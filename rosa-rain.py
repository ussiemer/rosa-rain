import pandas as pd
import io
import re
import os
import cairosvg

def csv_to_svg_table(csv_data, svg_width=800):
    """
    Erstellt eine SVG-Tabelle, die nur die Zweitstimmen anzeigt,
    ohne die G/V-Spalte und ohne die Spaltenüberschriften.
    Zeilen für AfD und III. Weg werden rot hervorgehoben.
    """
    csv_file = io.StringIO(csv_data)

    # Read and discard the first two lines
    csv_file.readline()
    csv_file.readline()

    # Read the third line to get the title, which is now the table title.
    title_raw = csv_file.readline().strip()

    # Use regex to get the text before the commas and remove the "Amtliches Endergebnis" part
    match = re.search(r'^(.*?),+', title_raw)
    if match:
        title_raw = match.group(1).strip()

    # Check if the title is empty and fall back to a placeholder
    if not title_raw:
        title_raw = "Wahlergebnis"

    # Read the rest of the data, specifying the semicolon separator
    try:
        df = pd.read_csv(csv_file, header=None, sep=';')
    except pd.errors.ParserError:
        raise ValueError("The CSV file could not be parsed with a semicolon delimiter.")

    # Check if the DataFrame has at least 6 columns (indices 0 to 5)
    if df.shape[1] < 6:
        raise ValueError(f"The CSV file does not have the expected number of columns. Found {df.shape[1]} columns.")

    # Select Merkmal and Zweitstimmen columns (indices 0, 4, 5)
    df = df.iloc[:, [0, 4, 5]].copy()

    # Set the column headers
    df.columns = ['Merkmal', 'Anzahl', 'Anteil']

    # Filter out rows that are not parties
    df = df[~df['Merkmal'].isin(['Wahlberechtigte', 'Wählende', 'Ungültige Stimmen', 'Gültige Stimmen', 'Sonstige Direktbewerbende', 'Gewinn/Verlust in Prozent'])]

    # Filter out rows where the 'Anzahl' column has a hyphen "-"
    df = df[df['Anzahl'] != '-']
    df = df.dropna(subset=['Merkmal'])

    # Reset index after filtering to prevent issues with row-based operations later
    df.reset_index(drop=True, inplace=True)

    # SVG parameters
    row_height = 25
    col_widths = [200, 100, 150]
    table_width = sum(col_widths)

    # Calculate x_offset to center the table
    x_offset = (svg_width - table_width) / 2
    y_offset = 497

    # New table font size
    table_font_size = 10.5

    svg_content = ''
    y_pos = y_offset + 30

    # Title
    svg_content += f'<text x="{x_offset + table_width/2}" y="{y_pos}" font-family="DejaVu Sans" font-size="16" text-anchor="middle" font-weight="bold">{title_raw}</text>\n'

    y_pos += 10.5

    # Draw horizontal header line
    y_pos += 15

    # Draw table rows with conditional styling
    for index, row in df.iterrows():
        x_pos_cumulative = x_offset

        background_color = "#ffffff"
        text_color = "#000000"
        if row['Merkmal'] in ['AfD', 'III. Weg']:
            background_color = "#e53935"
            text_color = "#ffffff"

        svg_content += f'<rect x="{x_offset}" y="{y_pos-18}" width="{sum(col_widths)}" height="{row_height}" style="fill:{background_color};stroke-width:0" />\n'

        for i, col_name in enumerate(df.columns):
            col_value = row[col_name]

            if i == 0:
                svg_content += f'<text x="{x_pos_cumulative + 5}" y="{y_pos}" font-family="DejaVu Sans" font-size="{table_font_size}" text-anchor="start" fill="{text_color}">{col_value}</text>\n'
                x_pos_cumulative += col_widths[i]
            else:
                svg_content += f'<text x="{x_pos_cumulative + col_widths[i]/2}" y="{y_pos}" font-family="DejaVu Sans" font-size="{table_font_size}" text-anchor="middle" fill="{text_color}">{col_value}</text>\n'
                x_pos_cumulative += col_widths[i]

        y_pos += row_height

    return svg_content

# The rest of your main script remains the same.
# --- Main script ---
directory = 'results'
output_dir = 'output_svgs'
pdf_output_dir = 'output_pdfs'
svg_template_file = 'rr.svg'

os.makedirs(output_dir, exist_ok=True)
os.makedirs(pdf_output_dir, exist_ok=True)

if not os.path.isdir(directory):
    print(f"Error: The directory '{directory}' was not found.")
else:
    try:
        with open(svg_template_file, 'r', encoding='utf-8') as f:
            svg_doc = f.read()
    except FileNotFoundError:
        print(f"Error: The template file '{svg_template_file}' was not found.")
        exit()

    pattern = re.compile(r'(<g\s+inkscape:groupmode="layer"\s+id="layer3"\s+inkscape:label="ElectionTable">).*?(</g>)', re.DOTALL)

    match = pattern.search(svg_doc)

    if not match:
        print("Fehler: Das angegebene SVG-Gruppen-Tag konnte nicht gefunden werden.")
    else:
        for filename in os.listdir(directory):
            if filename.endswith('.csv'):
                csv_file_path = os.path.join(directory, filename)

                try:
                    with open(csv_file_path, 'r', encoding='utf-8') as f:
                        csv_string = f.read()

                    svg_table = csv_to_svg_table(csv_string)
                    start_group = match.group(1)
                    end_group = match.group(2)
                    new_group_content = f'{start_group}\n{svg_table}\n{end_group}'
                    new_svg_doc = pattern.sub(new_group_content, svg_doc)
                    output_filename = os.path.splitext(filename)[0]

                    # --- SVG Output ---
                    svg_output_path = os.path.join(output_dir, output_filename + '.svg')
                    with open(svg_output_path, 'w', encoding='utf-8') as f:
                        f.write(new_svg_doc)
                    print(f"SVG-Datei '{svg_output_path}' erfolgreich erstellt!")

                    # --- PDF Output ---
                    pdf_output_path = os.path.join(pdf_output_dir, output_filename + '.pdf')
                    cairosvg.svg2pdf(bytestring=new_svg_doc.encode('utf-8'), write_to=pdf_output_path)
                    print(f"PDF-Datei '{pdf_output_path}' erfolgreich erstellt!")

                except FileNotFoundError:
                    print(f"Fehler: Die Datei '{csv_file_path}' wurde nicht gefunden.")
                except Exception as e:
                    print(f"Ein unerwarteter Fehler ist bei der Verarbeitung von '{filename}' aufgetreten: {e}")
