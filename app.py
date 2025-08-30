import pandas as pd
import glob
import os
import re
from quart import Quart, request, jsonify, render_template, send_from_directory
import graphene
import asyncio
import traceback
import csv
import numpy as np

df = None
schema = None
data_loaded_event = asyncio.Event()

def clean_source_file_name(file_name: str) -> str:
    """
    Cleans up a source file name by removing the prefix, extension, and underscores,
    and replacing them with spaces.
    """
    name_without_ext = os.path.splitext(file_name)[0]
    # This regex is a bit more robust for the new filename format
    cleaned_name = re.sub(r'^[a-z]+_\d+_\d+_', '', name_without_ext)
    cleaned_name = cleaned_name.replace('_', ' ')
    return cleaned_name.strip()

def load_all_csvs(folder_path: str) -> pd.DataFrame:
    all_files = glob.glob(os.path.join(folder_path, "*.csv"))
    print("Loading CSV files:", all_files)
    df_list = []

    standard_columns = [
        'Merkmal',
        'Erststimmen_Anzahl',
        'Erststimmen_Anteil',
        'Erststimmen_Gewinn',
        'Zweitstimmen_Anzahl',
        'Zweitstimmen_Anteil',
        'Zweitstimmen_Gewinn'
    ]

    for file in all_files:
        try:
            temp_df = pd.read_csv(file, sep=';', on_bad_lines='skip')
            temp_df.columns = standard_columns

            temp_df = temp_df.apply(lambda x: x.astype(str).str.replace(',', '.', regex=False).str.replace('%', '', regex=False) if x.name != 'Merkmal' else x)
            temp_df[standard_columns[1:]] = temp_df[standard_columns[1:]].apply(pd.to_numeric, errors='coerce')

            base_name = os.path.basename(file)

            # Extract electoral type and IDs using a more flexible regex
            electoral_match = re.search(r'^([a-z]+)_(\d+)_(\d+)', base_name)

            electoral_type = electoral_match.group(1) if electoral_match else None
            wahlkreis_id = electoral_match.group(2) if electoral_match else None
            specific_id = electoral_match.group(3) if electoral_match else None

            # Keep the original 'districtId' column name but now with the new 'specificId'
            # Also add new columns for the wahlkreisId and sourceType
            temp_df['districtId'] = specific_id if specific_id else None
            temp_df['wahlkreisId'] = f"wk{wahlkreis_id}" if wahlkreis_id else None
            temp_df['sourceType'] = electoral_type
            temp_df['locationName'] = clean_source_file_name(base_name)
            temp_df['sourceFile'] = base_name

            df_list.append(temp_df)
        except Exception as e:
            print(f"Error reading and processing file {file}: {e}")
            traceback.print_exc()
            continue

    if not df_list:
        return pd.DataFrame()

    df = pd.concat(df_list, ignore_index=True)

    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].fillna(0)

    print("DataFrame loaded with columns:", df.columns.tolist())
    return df

def create_graphql_type(df: pd.DataFrame) -> graphene.ObjectType:
    if df.empty or not len(df.columns):
        print("DataFrame is empty, cannot create GraphQL type.")
        class CsvType(graphene.ObjectType):
            placeholder = graphene.String()
        return CsvType

    attrs = {}
    for col in df.columns:
        if col in ['Merkmal', 'sourceFile', 'locationName', 'districtId', 'wahlkreisId', 'sourceType']:
            attrs[col] = graphene.Field(graphene.String)
            continue

        col_type = graphene.String

        try:
            if pd.api.types.is_float_dtype(df[col]):
                col_type = graphene.Float
            elif pd.api.types.is_integer_dtype(df[col]):
                col_type = graphene.Int
        except TypeError:
            pass

        attrs[col] = graphene.Field(col_type)

    return type('CsvType', (graphene.ObjectType,), attrs)

def create_schema_from_df(df: pd.DataFrame):
    global schema
    print("DataFrame columns before schema creation:", df.columns.tolist())
    print("DataFrame head:\n", df.head())
    if df.empty or not len(df.columns):
        print("DataFrame is empty or has no columns, using EmptyQuery.")
        class EmptyQuery(graphene.ObjectType):
            hello = graphene.String()
            def resolve_hello(self, info):
                return "Hello, the database is empty or malformed!"
        schema = graphene.Schema(query=EmptyQuery)
        return
    CsvType = create_graphql_type(df)

    class Query(graphene.ObjectType):
        allData = graphene.List(
            CsvType,
            **{col: graphene.String(description=f"Filter by {col}") for col in df.columns}
        )
        async def resolve_allData(self, info, **kwargs):
            await asyncio.sleep(0.01)
            results = df.copy()
            for key, value in kwargs.items():
                if key in results.columns and value is not None and value != '':
                    results = results[results[key].astype(str).str.contains(value, case=False, na=False)]

            records = results.to_dict('records')

            if isinstance(records, dict):
                return [records]

            return records
    schema = graphene.Schema(query=Query)


# Function to geolocate all polling places e.g.
# only if districtId has 16 digits (1207353041890003) it is a polling place
# the last 4 digits are the local polling place
# geolocate the name / place / organisation using geocoding_service.py in the background
# add lat lon to the graphql output

app = Quart(__name__)

async def load_data_and_create_schema():
    global df, schema
    print("Starting data loading in background...")
    try:
        df = await asyncio.to_thread(load_all_csvs, 'results')
        create_schema_from_df(df)
        print("GraphQL schema created successfully!")
        print("Final DataFrame Columns:", df.columns.tolist())
        print("You can query with these exact field names:")
        for col in df.columns:
            print(f"   {col}")
    finally:
        data_loaded_event.set()

@app.before_serving
async def start_background_task():
    app.add_background_task(load_data_and_create_schema)

@app.route("/")
async def index():
    return await render_template('index.html')

@app.route("/graphql", methods=["POST"])
async def graphql_endpoint():
    await data_loaded_event.wait()

    if schema is None:
        return jsonify({"errors": [{"message": "API not initialized."}]}), 500
    try:
        data = await request.get_json()
        query = data.get("query")
        variables = data.get("variables")

        result = await schema.execute_async(query, variable_values=variables)

        response = {}
        if result.errors:
            response["errors"] = [{"message": str(e)} for e in result.errors]
        if result.data:
            response["data"] = result.data
        return jsonify(response)
    except Exception as e:
        print(f"GraphQL error: {e}")
        return jsonify({"errors": [{"message": str(e)}]}), 400

# In your app.py file, add this new route:
from quart import jsonify

@app.route("/api/polling-places")
async def get_polling_places():
    """
    Returns a list of all polling place IDs (filenames) in the locations directory.
    """
    locations_dir = 'static/data/locations'
    try:
        # List all files, remove the .csv extension, and return
        polling_place_ids = [os.path.splitext(f)[0] for f in os.listdir(locations_dir) if f.endswith('.csv')]
        return jsonify(polling_place_ids)
    except FileNotFoundError:
        return jsonify({"error": "Locations directory not found."}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/static/<path:filename>")
async def static_files(filename):
    # Add a case here to redirect favicon.ico to the SVG file.
    if filename == 'favicon.ico':
        return redirect('/static/images/Antifalogo_alt2.svg')
    return await send_from_directory('static', filename)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
