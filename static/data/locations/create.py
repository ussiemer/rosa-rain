import csv

# Data for the WBZ locations
data = [
    ["WBZ 8 Spremberg ehem. Hort Georgenberg", 51.5756, 14.3854],
    ["WBZ 9 Spremberg Sportplatz 1862", 51.5683, 14.3683],
    ["WBZ 10 Spremberg Wiesenwegschule", 51.5695, 14.3831],
    ["WBZ 11 Spremberg Schule mit Förderschwerpunkt Lernen", 51.5746, 14.3871],
    ["WBZ 12 Spremberg Kita Kollerberg", 51.5721, 14.3719],
    ["WBZ 13 Spremberg Grundschule Kollerberg", 51.5721, 14.3719],
    ["WBZ 14 OT Schwarze Pumpe I Grundschule Schwarze Pumpe", 51.5459, 14.5029],
    ["WBZ 15 OT Schwarze Pumpe II Kita Kinderland", 51.5459, 14.5029],
    ["WBZ 16 OT Trattendorf I BWS Behindertenwerk Cafe Wilhelmsthal", 51.5613, 14.3716],
    ["WBZ 17 OT Trattendorf II Stadtverwaltung DG 3", 51.5638, 14.3995],
    ["WBZ 18 OT Sellessen Heidegrundschule Sellessen", 51.5768, 14.4172],
    ["WBZ 19 OT Weskow Schilfhütte", 51.5543, 14.3615],
    ["WBZ 20 OT Haidemühl Dorfgemeinschaftshaus Haidemühl", 51.606, 14.4533],
    ["WBZ 21 OT Cantdorf Kita Cantdorf", 51.5748, 14.4373],
    ["WBZ 22 OT Terpe Feuerwehrgerätehaus Terpe", 51.5478, 14.4752],
    ["WBZ 23 OT Lieskau Dorfgemeinschaftshaus Lieskau", 51.5367, 14.4697],
    ["WBZ 24 OT Graustein Turnhalle Kita Graustein", 51.5284, 14.4449],
    ["WBZ 25 OT Groß Luja Gemeindezentrum Groß Luja", 51.5173, 14.4093],
    ["WBZ 26 OT Hornow Gemeindehaus Hornow", 51.5152, 14.4851],
    ["WBZ 27 OT Wadelsdorf Gemeindebüro Wadelsdorf", 51.5172, 14.507],
    ["WBZ 28 OT Türkendorf Gemeindezentrum Türkendorf", 51.5312, 14.5249],
    ["WBZ 29 OT Schönheide Dorfgemeinschaftshaus Schönheide", 51.503, 14.5161]
]

# Starting ID for the filenames
start_id = 1207103723720008

# Iterate through the data and create a separate CSV file for each entry
for i, row_data in enumerate(data):
    filename = f"{start_id + i}.csv"
    with open(filename, 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        # Write the header row
        writer.writerow(["name", "lat", "lon"])
        # Write the single data row
        writer.writerow(row_data)

    print(f"The file '{filename}' has been created successfully.")
