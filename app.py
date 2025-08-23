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

def load_all_csvs(folder_path: str) -> pd.DataFrame:
    all_files = glob.glob(os.path.join(folder_path, "*.csv"))
    print("Loading CSV files:", all_files)
    df_list = []

    # Define a single, consistent header
    standard_columns = [
        'Merkmal',
        'Erststimmen_Anzahl', 'Erststimmen_Anteil', 'Erststimmen_Gewinn',
        'Zweitstimmen_Anzahl', 'Zweitstimmen_Anteil', 'Zweitstimmen_Gewinn',
    ]

    for file in all_files:
        try:
            # Read the file, skipping the original headers
            temp_df = pd.read_csv(file, sep=';', skiprows=4, header=None)

            # Check if the number of columns matches the standard
            if temp_df.shape[1] != len(standard_columns):
                print(f"Warning: Column count mismatch in {file}. Skipping this file.")
                continue

            # Assign the standard column names
            temp_df.columns = standard_columns

            # Use explicit conversion and filling to handle data types.
            for col in temp_df.columns:
                if col == 'Merkmal' or col == 'sourceFile':
                    continue

                # Replace common non-numeric values
                temp_df[col] = temp_df[col].astype(str).str.strip().str.replace(',', '.', regex=False)
                temp_df[col] = temp_df[col].str.replace('%', '', regex=False)

                # Coerce to numeric, filling NaNs with 0
                temp_df[col] = pd.to_numeric(temp_df[col], errors='coerce').fillna(0)

            temp_df['sourceFile'] = os.path.basename(file)
            df_list.append(temp_df)

        except Exception as e:
            print(f"Error reading and processing file {file}: {e}")
            traceback.print_exc()
            continue

    if not df_list:
        return pd.DataFrame()

    df = pd.concat(df_list, ignore_index=True)

    # Final check and fill for any remaining NaNs
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
        if col == 'Merkmal':
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
            print(f"    {col}")
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
    # Wait for the data to be loaded before processing the query
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
    app.run(debug=False)
