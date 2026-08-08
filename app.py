from flask import Flask, render_template, request
import pandas as pd
import plotly.express as px
import plotly.io as pio
import os
from flask import send_file
from io import BytesIO
app = Flask(__name__)
@app.route("/export-excel", methods=["POST"])
def export_excel():

    filename = request.form.get("filename")
    x_column = request.form.get("x_column")
    y_column = request.form.get("y_column")

    filepath = os.path.join(
        app.config["UPLOAD_FOLDER"],
        filename
    )

    df = read_file(filepath)

    df.columns = [
        str(col).strip()
        for col in df.columns
    ]

    # Données valides
    valid = df[[x_column, y_column]].dropna()

    # Analyse
    analyse = (
        valid
        .groupby([x_column, y_column])
        .size()
        .reset_index(name="Effectif")
    )

    # Pourcentage
    total = analyse["Effectif"].sum()

    analyse["Pourcentage"] = (
        analyse["Effectif"] / total * 100
    ).round(2)

    # Statistiques
    statistiques = pd.DataFrame({
        "Indicateur": [
            "Total réponses",
            "Réponses valides",
            "Réponses manquantes X",
            "Réponses manquantes Y"
        ],
        "Valeur": [
            len(df),
            len(valid),
            int(df[x_column].isna().sum()),
            int(df[y_column].isna().sum())
        ]
    })

    # Création du fichier Excel en mémoire
    output = BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl"
    ) as writer:

        analyse.to_excel(
            writer,
            sheet_name="Analyse",
            index=False
        )

        statistiques.to_excel(
            writer,
            sheet_name="Statistiques",
            index=False
        )

        df.to_excel(
            writer,
            sheet_name="Donnees",
            index=False
        )

    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="analyse_resultat.xlsx",
        mimetype=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"xlsx", "csv"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def read_file(filepath):
    extension = filepath.rsplit(".", 1)[1].lower()

    if extension == "csv":
        return pd.read_csv(filepath)

    return pd.read_excel(filepath)


@app.route("/", methods=["GET", "POST"])
def index():

    columns = []
    chart = None
    stats = None
    error = None

    if request.method == "POST":

        # =========================
        # IMPORT DU FICHIER
        # =========================

        if "file" in request.files:

            file = request.files["file"]

            if file.filename == "":
                error = "Veuillez sélectionner un fichier."

            elif not allowed_file(file.filename):
                error = "Format non accepté. Utilisez Excel (.xlsx) ou CSV."

            else:

                filepath = os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    file.filename
                )

                file.save(filepath)

                try:
                    df = read_file(filepath)

                    # Nettoyage des noms de colonnes
                    df.columns = [
                        str(col).strip()
                        for col in df.columns
                    ]

                    columns = df.columns.tolist()

                    # Sauvegarde temporaire du nom du fichier
                    return render_template(
                        "index.html",
                        columns=columns,
                        filename=file.filename,
                        error=None
                    )

                except Exception as e:
                    error = f"Erreur lors de la lecture : {str(e)}"

        # =========================
        # GENERATION DU GRAPHIQUE
        # =========================

        elif "generate" in request.form:

            filename = request.form.get("filename")
            x_column = request.form.get("x_column")
            y_column = request.form.get("y_column")
            chart_type = request.form.get("chart_type")

            filepath = os.path.join(
                app.config["UPLOAD_FOLDER"],
                filename
            )

            try:

                df = read_file(filepath)

                df.columns = [
                    str(col).strip()
                    for col in df.columns
                ]

                columns = df.columns.tolist()

                if x_column not in df.columns:
                    raise ValueError("Variable X invalide.")

                if y_column not in df.columns:
                    raise ValueError("Variable Y invalide.")

               # =========================
                # STATISTIQUES
                # =========================

                total = len(df)

                valid = df[[x_column, y_column]].dropna()

                missing_x = df[x_column].isna().sum()
                missing_y = df[y_column].isna().sum()

                # Tableau de fréquences
                frequency = (
                    valid[x_column]
                    .value_counts()
                    .reset_index()
                )

                frequency.columns = [
                    x_column,
                    "Effectif"
                ]

                frequency["Pourcentage"] = (
                    frequency["Effectif"] / len(valid) * 100
                ).round(2)

                stats = {
                     "total": total,
                    "valid": len(valid),
                    "missing_x": int(missing_x),
                    "missing_y": int(missing_y),
                    "x_name": x_column,
                    "y_name": y_column,
                    "frequency": frequency.to_dict("records")
                }
                # =========================
                # PREPARATION DES DONNEES
                # =========================

                if chart_type in ["bar", "pie"]:

                    data = (
                        valid
                        .groupby([x_column, y_column])
                        .size()
                        .reset_index(name="Nombre")
                    )

                    if chart_type == "bar":

                        fig = px.bar(
                            data,
                            x=x_column,
                            y="Nombre",
                            color=y_column,
                            barmode="group",
                            title=f"{y_column} selon {x_column}"
                        )

                    else:

                        # Pour le graphique circulaire,
                        # on utilise la variable Y
                        pie_data = (
                            valid[y_column]
                            .value_counts()
                            .reset_index()
                        )

                        pie_data.columns = [
                            y_column,
                            "Nombre"
                        ]

                        fig = px.pie(
                            pie_data,
                            names=y_column,
                            values="Nombre",
                            title=f"Répartition de {y_column}"
                        )

                elif chart_type == "line":

                    data = (
                        valid
                        .groupby(x_column)
                        .size()
                        .reset_index(name="Nombre")
                    )

                    fig = px.line(
                        data,
                        x=x_column,
                        y="Nombre",
                        markers=True,
                        title=f"Évolution de {y_column}"
                    )

                elif chart_type == "scatter":

                    numeric_data = valid.copy()

                    numeric_data[x_column] = pd.to_numeric(
                        numeric_data[x_column],
                        errors="coerce"
                    )

                    numeric_data[y_column] = pd.to_numeric(
                        numeric_data[y_column],
                        errors="coerce"
                    )

                    numeric_data = numeric_data.dropna()

                    fig = px.scatter(
                        numeric_data,
                        x=x_column,
                        y=y_column,
                        title=f"{y_column} selon {x_column}"
                    )

                else:
                    raise ValueError(
                        "Type de graphique non reconnu."
                    )

                # =========================
                # STYLE DU GRAPHIQUE
                # =========================

                fig.update_layout(
                    template="plotly_white",
                    height=550,
                    margin=dict(
                        l=40,
                        r=40,
                        t=80,
                        b=40
                    )
                )

                chart = pio.to_html(
                    fig,
                    full_html=False,
                    include_plotlyjs="cdn"
                )

            except Exception as e:

                error = f"Erreur : {str(e)}"

    return render_template(
        "index.html",
        columns=columns,
        chart=chart,
        stats=stats,
        error=error,
        filename=request.form.get("filename", "")
    )


if __name__ == "__main__":
    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )