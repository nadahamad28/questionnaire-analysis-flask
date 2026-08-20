from flask import Flask, render_template, request, send_file
import pandas as pd
import plotly.express as px
import plotly.io as pio
import os
from io import BytesIO

app = Flask(__name__)

# Vercel allows temporary files in /tmp
UPLOAD_FOLDER = "/tmp/uploads"

ALLOWED_EXTENSIONS = {"xlsx", "csv"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# =========================================================
# VERIFICATION EXTENSION
# =========================================================

def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


# =========================================================
# LECTURE FICHIER
# =========================================================

def read_file(filepath):

    extension = filepath.rsplit(".", 1)[1].lower()

    if extension == "csv":
        return pd.read_csv(filepath)

    return pd.read_excel(filepath)


# =========================================================
# PAGE PRINCIPALE
# =========================================================

@app.route("/", methods=["GET", "POST"])
def index():

    columns = []
    charts = []
    stats = []
    sexe_stats = []

    error = None
    filename = ""

    # =====================================================
    # POST
    # =====================================================

    if request.method == "POST":

        # =================================================
        # IMPORT DU FICHIER
        # =================================================

        if "file" in request.files:

            file = request.files["file"]

            if file.filename == "":
                error = "Veuillez sélectionner un fichier."

            elif not allowed_file(file.filename):
                error = "Format non accepté. Utilisez Excel (.xlsx) ou CSV."

            else:

                filename = file.filename

                filepath = os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    filename
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

                    # =====================================
                    # STATISTIQUES SEXE
                    # =====================================

                    if "Sexe" in df.columns:

                        sexe_frequency = (
                            df["Sexe"]
                            .dropna()
                            .value_counts()
                            .reset_index()
                        )

                        sexe_frequency.columns = [
                            "Sexe",
                            "Effectif"
                        ]

                        total_sexe = sexe_frequency["Effectif"].sum()

                        if total_sexe > 0:

                            sexe_frequency["Pourcentage"] = (
                                sexe_frequency["Effectif"]
                                / total_sexe
                                * 100
                            ).round(2)

                        else:

                            sexe_frequency["Pourcentage"] = 0

                        sexe_stats = sexe_frequency.to_dict(
                            "records"
                        )

                    return render_template(
                        "index.html",
                        columns=columns,
                        charts=[],
                        stats=[],
                        sexe_stats=sexe_stats,
                        filename=filename,
                        error=None
                    )

                except Exception as e:

                    error = f"Erreur lors de la lecture : {str(e)}"

        # =================================================
        # GENERATION DES GRAPHIQUES
        # =================================================

        elif "generate" in request.form:

            filename = request.form.get(
                "filename",
                ""
            )

            # Plusieurs X et plusieurs Y
            x_columns = request.form.getlist(
                "x_column"
            )

            y_columns = request.form.getlist(
                "y_column"
            )

            chart_type = request.form.get(
                "chart_type",
                "bar"
            )

            if not x_columns:

                error = (
                    "Veuillez sélectionner au moins "
                    "une variable X."
                )

            elif not y_columns:

                error = (
                    "Veuillez sélectionner au moins "
                    "une variable Y."
                )

            else:

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

                    # =====================================
                    # VERIFICATION DES COLONNES
                    # =====================================

                    invalid_x = [
                        col
                        for col in x_columns
                        if col not in df.columns
                    ]

                    invalid_y = [
                        col
                        for col in y_columns
                        if col not in df.columns
                    ]

                    if invalid_x:

                        raise ValueError(
                            "Variable(s) X invalide(s) : "
                            + ", ".join(invalid_x)
                        )

                    if invalid_y:

                        raise ValueError(
                            "Variable(s) Y invalide(s) : "
                            + ", ".join(invalid_y)
                        )

                    # =====================================
                    # STATISTIQUES SEXE
                    # =====================================

                    if "Sexe" in df.columns:

                        sexe_frequency = (
                            df["Sexe"]
                            .dropna()
                            .value_counts()
                            .reset_index()
                        )

                        sexe_frequency.columns = [
                            "Sexe",
                            "Effectif"
                        ]

                        total_sexe = (
                            sexe_frequency["Effectif"].sum()
                        )

                        if total_sexe > 0:

                            sexe_frequency["Pourcentage"] = (
                                sexe_frequency["Effectif"]
                                / total_sexe
                                * 100
                            ).round(2)

                        else:

                            sexe_frequency["Pourcentage"] = 0

                        sexe_stats = (
                            sexe_frequency.to_dict("records")
                        )

                    # =====================================
                    # X × Y
                    # =====================================

                    for x_column in x_columns:

                        for y_column in y_columns:

                            valid = (
                                df[
                                    [x_column, y_column]
                                ]
                                .dropna()
                            )

                            if valid.empty:
                                continue

                            # =================================
                            # STATISTIQUES
                            # =================================

                            total = len(df)

                            valid_count = len(valid)

                            missing_x = int(
                                df[x_column].isna().sum()
                            )

                            missing_y = int(
                                df[y_column].isna().sum()
                            )

                            stats.append({
                                "x_name": x_column,
                                "y_name": y_column,
                                "total": total,
                                "valid": valid_count,
                                "missing_x": missing_x,
                                "missing_y": missing_y
                            })

                            # =================================
                            # GRAPHIQUE BAR
                            # =================================

                            if chart_type == "bar":

                                data = (
                                    valid
                                    .groupby(
                                        [x_column, y_column]
                                    )
                                    .size()
                                    .reset_index(
                                        name="Nombre"
                                    )
                                )

                                fig = px.bar(
                                    data,
                                    x=x_column,
                                    y="Nombre",
                                    color=y_column,
                                    barmode="group",
                                    title=(
                                        f"{y_column} "
                                        f"selon {x_column}"
                                    )
                                )

                            # =================================
                            # GRAPHIQUE PIE
                            # =================================

                            elif chart_type == "pie":

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
                                    title=(
                                        f"Répartition de "
                                        f"{y_column}"
                                    )
                                )

                            # =================================
                            # GRAPHIQUE LINE
                            # =================================

                            elif chart_type == "line":

                                data = (
                                    valid
                                    .groupby(x_column)
                                    .size()
                                    .reset_index(
                                        name="Nombre"
                                    )
                                )

                                fig = px.line(
                                    data,
                                    x=x_column,
                                    y="Nombre",
                                    markers=True,
                                    title=(
                                        f"Évolution de "
                                        f"{x_column}"
                                    )
                                )

                            # =================================
                            # GRAPHIQUE SCATTER
                            # =================================

                            elif chart_type == "scatter":

                                numeric_data = valid.copy()

                                numeric_data[x_column] = (
                                    pd.to_numeric(
                                        numeric_data[x_column],
                                        errors="coerce"
                                    )
                                )

                                numeric_data[y_column] = (
                                    pd.to_numeric(
                                        numeric_data[y_column],
                                        errors="coerce"
                                    )
                                )

                                numeric_data = (
                                    numeric_data.dropna()
                                )

                                if numeric_data.empty:
                                    continue

                                fig = px.scatter(
                                    numeric_data,
                                    x=x_column,
                                    y=y_column,
                                    title=(
                                        f"{y_column} "
                                        f"selon {x_column}"
                                    )
                                )

                            else:

                                raise ValueError(
                                    "Type de graphique "
                                    "non reconnu."
                                )

                            # =================================
                            # STYLE
                            # =================================

                            fig.update_layout(
                                template="plotly_white",
                                height=500,
                                margin=dict(
                                    l=40,
                                    r=40,
                                    t=80,
                                    b=40
                                )
                            )

                            # =================================
                            # CONVERSION HTML
                            # =================================

                            charts.append({
                                "x_name": x_column,
                                "y_name": y_column,
                                "html": pio.to_html(
                                    fig,
                                    full_html=False,
                                    include_plotlyjs="cdn"
                                )
                            })

                except Exception as e:

                    error = f"Erreur : {str(e)}"

    # =====================================================
    # AFFICHAGE
    # =====================================================

    return render_template(
        "index.html",
        columns=columns,
        charts=charts,
        stats=stats,
        sexe_stats=sexe_stats,
        error=error,
        filename=filename
    )


# =========================================================
# EXPORT EXCEL
# =========================================================

@app.route("/export-excel", methods=["POST"])
def export_excel():

    filename = request.form.get(
        "filename",
        ""
    )

    # Plusieurs X et Y
    x_columns = request.form.getlist(
        "x_column"
    )

    y_columns = request.form.getlist(
        "y_column"
    )

    if not x_columns or not y_columns:

        return (
            "Veuillez sélectionner au moins "
            "un X et un Y.",
            400
        )

    filepath = os.path.join(
        app.config["UPLOAD_FOLDER"],
        filename
    )

    # Vérifier que le fichier existe
    if not os.path.exists(filepath):

        return (
            "Fichier introuvable.",
            404
        )

    try:

        # ==============================================
        # LECTURE
        # ==============================================

        df = read_file(filepath)

        df.columns = [
            str(col).strip()
            for col in df.columns
        ]

        # ==============================================
        # VERIFICATION COLONNES
        # ==============================================

        invalid_x = [
            col
            for col in x_columns
            if col not in df.columns
        ]

        invalid_y = [
            col
            for col in y_columns
            if col not in df.columns
        ]

        if invalid_x:

            return (
                "Variable(s) X invalide(s) : "
                + ", ".join(invalid_x),
                400
            )

        if invalid_y:

            return (
                "Variable(s) Y invalide(s) : "
                + ", ".join(invalid_y),
                400
            )

        # ==============================================
        # CREATION EXCEL EN MEMOIRE
        # ==============================================

        output = BytesIO()

        with pd.ExcelWriter(
            output,
            engine="openpyxl"
        ) as writer:

            # ==========================================
            # STATISTIQUES SEXE
            # ==========================================

            if "Sexe" in df.columns:

                sexe_frequency = (
                    df["Sexe"]
                    .dropna()
                    .value_counts()
                    .reset_index()
                )

                sexe_frequency.columns = [
                    "Sexe",
                    "Effectif"
                ]

                total_sexe = (
                    sexe_frequency["Effectif"].sum()
                )

                if total_sexe > 0:

                    sexe_frequency["Pourcentage"] = (
                        sexe_frequency["Effectif"]
                        / total_sexe
                        * 100
                    ).round(2)

                else:

                    sexe_frequency["Pourcentage"] = 0

                sexe_frequency.to_excel(
                    writer,
                    sheet_name="Statistiques Sexe",
                    index=False
                )

            # ==========================================
            # UNE FEUILLE PAR COMBINAISON X / Y
            # ==========================================

            used_sheet_names = set()

            for x_column in x_columns:

                for y_column in y_columns:

                    valid = (
                        df[
                            [x_column, y_column]
                        ]
                        .dropna()
                    )

                    analyse = (
                        valid
                        .groupby(
                            [x_column, y_column]
                        )
                        .size()
                        .reset_index(
                            name="Effectif"
                        )
                    )

                    total = analyse["Effectif"].sum()

                    if total > 0:

                        analyse["Pourcentage"] = (
                            analyse["Effectif"]
                            / total
                            * 100
                        ).round(2)

                    else:

                        analyse["Pourcentage"] = 0

                    # ==================================
                    # NOM FEUILLE
                    # ==================================

                    sheet_name = (
                        f"{x_column[:12]}_{y_column[:12]}"
                    )

                    sheet_name = sheet_name[:31]

                    # Excel interdit certains caractères
                    invalid_chars = [
                        "\\",
                        "/",
                        "*",
                        "?",
                        ":",
                        "[",
                        "]"
                    ]

                    for char in invalid_chars:
                        sheet_name = sheet_name.replace(
                            char,
                            "_"
                        )

                    # Eviter les doublons
                    original_name = sheet_name
                    counter = 1

                    while sheet_name in used_sheet_names:

                        suffix = f"_{counter}"

                        sheet_name = (
                            original_name[
                                :31 - len(suffix)
                            ]
                            + suffix
                        )

                        counter += 1

                    used_sheet_names.add(
                        sheet_name
                    )

                    analyse.to_excel(
                        writer,
                        sheet_name=sheet_name,
                        index=False
                    )

            # ==========================================
            # STATISTIQUES GLOBALES
            # ==========================================

            statistics_rows = []

            for x_column in x_columns:

                for y_column in y_columns:

                    valid = (
                        df[
                            [x_column, y_column]
                        ]
                        .dropna()
                    )

                    statistics_rows.append({
                        "X": x_column,
                        "Y": y_column,
                        "Total réponses": len(df),
                        "Réponses valides": len(valid),
                        "Réponses manquantes X":
                            int(
                                df[x_column]
                                .isna()
                                .sum()
                            ),
                        "Réponses manquantes Y":
                            int(
                                df[y_column]
                                .isna()
                                .sum()
                            )
                    })

            pd.DataFrame(
                statistics_rows
            ).to_excel(
                writer,
                sheet_name="Statistiques",
                index=False
            )

            # ==========================================
            # DONNEES ORIGINALES
            # ==========================================

            df.to_excel(
                writer,
                sheet_name="Donnees",
                index=False
            )

        # ==============================================
        # PREPARER LE FICHIER
        # ==============================================

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

    except Exception as e:

        return (
            f"Erreur lors de l'export : {str(e)}",
            500
        )


# =========================================================
# LANCEMENT
# =========================================================



  
if __name__ == "__main__":
    app.run(debug=True)