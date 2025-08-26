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
    # The new filename starts with "wahlkreis_XX_..."
    name_without_prefix = re.sub(r'^wahlkreis_\d+_', '', file_name)
    name_without_ext = os.path.splitext(name_without_prefix)[0]
    cleaned_name = name_without_ext.replace('_', ' ')
    return cleaned_name.strip()

def load_all_csvs(folder_path: str) -> pd.DataFrame:
    all_files = glob.glob(os.path.join(folder_path, "*.csv"))
    print("Loading CSV files:", all_files)
    df_list = []

    # New standard columns based on the new CSV output format
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
            # The new CSVs have a proper header, so no need to skip rows
            temp_df = pd.read_csv(file, sep=';', on_bad_lines='skip')

            # The columns in the new CSV are slightly different.
            # We will use the new standard columns and rename them to a more usable format.
            temp_df.columns = standard_columns

            # Convert types and clean data
            # Use .apply() for a more robust conversion across columns
            temp_df = temp_df.apply(lambda x: x.astype(str).str.replace(',', '.', regex=False).str.replace('%', '', regex=False) if x.name != 'Merkmal' else x)

            # Convert to float without rounding
            temp_df[standard_columns[1:]] = temp_df[standard_columns[1:]].apply(pd.to_numeric, errors='coerce')

            # Extract electoral district ID from the filename
            base_name = os.path.basename(file)
            electoral_id_match = re.search(r'^wahlkreis_(\d+)', base_name)

            # Keep the two-digit format
            electoral_id = electoral_id_match.group(1) if electoral_id_match else None

            temp_df['districtId'] = f"wk{electoral_id}" if electoral_id else None
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
        if col in ['Merkmal', 'sourceFile', 'locationName', 'districtId']:
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

@app.route("/static/<path:filename>")
async def static_files(filename):
    return await send_from_directory('static', filename)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
