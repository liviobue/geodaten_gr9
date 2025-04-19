import pandas as pd

# Inspect the income CSV
income_df = pd.read_csv('data/income_by_municipality_utf8.csv', header=None)
income_df.columns = ['id', 'municipality_name', 'population', 'income']
print("First few rows of income data:")
print(income_df.head())
print("\nNon-numeric income values:")
print(income_df[~income_df['income'].str.replace('.', '', 1).str.isnumeric()]['income'].unique())
print("\nMissing values:")
print(income_df.isna().sum())