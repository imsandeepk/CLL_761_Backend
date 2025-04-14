import os
import pandas as pd
import ast
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from flask import Flask, jsonify, request


app = Flask(__name__)
# Function to calculate CAGR
def calculate_cagr(price_series):
    start_value = price_series[0]
    end_value = price_series[-1]
    num_years = len(price_series) / 252  # Assuming 252 trading days in a year
    cagr = (end_value / start_value) ** (1 / num_years) - 1
    return cagr

# Function to calculate Maximum Drawdown
def calculate_max_drawdown(price_series):
    cumulative_return = price_series / price_series[0]
    peak = np.maximum.accumulate(cumulative_return)  # Use numpy's accumulate function to find the peak
    drawdown = (cumulative_return - peak) / peak
    max_drawdown = drawdown.min()
    return max_drawdown

# Function to calculate Sharpe Ratio
def calculate_sharpe_ratio(returns, risk_free_rate=0.08):
    excess_returns = returns - risk_free_rate
    avg_excess_return = np.mean(excess_returns)
    return_volatility = np.std(excess_returns)
    sharpe_ratio = avg_excess_return / return_volatility
    return sharpe_ratio

def portfolio_variance(weights, cov_matrix):
    return weights.T @ cov_matrix @ weights

def risk_constraint(weights, cov_matrix, risk_limit):
    return risk_limit - np.sqrt(portfolio_variance(weights, cov_matrix))

def calculate_cov_matrix_from_timeseries(asset_prices):
    asset_returns = asset_prices.pct_change(fill_method=None).dropna()
    cov_matrix = asset_returns.cov()
    
    return cov_matrix

def optimize_portfolio(cov_matrix, risk_limit, n_assets):
    initial_weights = np.ones(n_assets) / n_assets

    # Constraints (sum of weights = 1 and risk limit)
    constraints = [
        {'type': 'eq', 'fun': lambda weights: np.sum(weights) - 1},  # Sum of weights is 1
        {'type': 'ineq', 'fun': lambda weights: risk_constraint(weights, cov_matrix, risk_limit)}  # Risk limit
    ]
    
    # Bounds (no short selling, i.e., weights >= 0)
    bounds = [(0, 1) for _ in range(n_assets)]
    
    # Minimize the objective function
    result = minimize(portfolio_variance, initial_weights, args=(cov_matrix,), 
                      method='SLSQP', constraints=constraints, bounds=bounds)
    
    print(result.message)
    return result.x if result.success else None

def optimized_portfolio_time_series(asset_prices, weights):
    return (weights*asset_prices).sum(axis=1).to_frame("Portfolio Price")

def create_folio(risk_limit=0.1, year_from = "2023", to_print=["weights", "cagr", "max_drawdown", "sharpe_ratio", "portfolio_variance"]):
    #asset_prices = assets.loc[year_from:]
    asset_prices = asset_prices_100
    cov_matrix = calculate_cov_matrix_from_timeseries(asset_prices)
    print(f"Risk Limit = {risk_limit}")
    # Optimize portfolio weights
    optimal_weights = optimize_portfolio(cov_matrix, risk_limit, asset_prices.shape[1])
    if "weights" in to_print:
        print("Optimal Weights:", optimal_weights)

    folio_time_series = optimized_portfolio_time_series(asset_prices, optimal_weights).values

    if "cagr" in to_print:
        print(f"CAGR = {calculate_cagr(folio_time_series)}")
    if "max_drawdown" in to_print:
        print(f"Max drawdown = {calculate_max_drawdown(folio_time_series)}")
    if "sharpe_ratio" in to_print:
        print(f"Sharpe Ratio = {calculate_sharpe_ratio(folio_time_series)}")
    if "portfolio_variance" in to_print:
        print(f"Portfolio Stdev = {np.sqrt(portfolio_variance(optimal_weights, calculate_cov_matrix_from_timeseries(asset_prices)))}")
    print("--------------------------------------------------------")
    



# Define the folder path and output file
folder_path = './Index Fund Time series'  # Update this to the folder containing your CSV files
output_file = 'collated_prices.csv'  # Output CSV file name

# Initialize an empty DataFrame to hold the collated data
collated_df = pd.DataFrame()

# Loop through each CSV file in the folder
for file_name in os.listdir(folder_path):
    if file_name.endswith('.csv'):
        # Construct full file path
        file_path = os.path.join(folder_path, file_name)
        
        # Read the CSV file, assuming it contains 'Date' and 'Price' columns
        # Specify dayfirst=True to interpret 'DD/MM/YY' format correctly
        df = pd.read_csv(file_path, usecols=['Date', 'Price'], dayfirst=True, parse_dates=['Date'])
        
        # Rename the 'Price' column to the file name (without extension)
        df.rename(columns={'Price': file_name.split('.')[0]}, inplace=True)
        
        # Merge this file's data with the collated DataFrame
        if collated_df.empty:
            # If the collated DataFrame is empty, initialize it with the first file's data
            collated_df = df
        else:
            # Otherwise, merge on 'Date'
            collated_df = pd.merge(collated_df, df, on='Date', how='outer')

# Save the collated DataFrame to a new CSV file
collated_df.to_csv(output_file, index=False)

def results(assests_selected, risk_limit=0.15):
    assets = pd.read_csv('collated_prices.csv', index_col='Date', parse_dates=True,
                            dtype=float, thousands=",", header=0)

    assets2 = assets.loc["2019-01-02":"2024-09-01"]
    assets2.loc["2019-01-02"]
    asset_prices = assets2[assests_selected]
    asset_prices.bfill(inplace=True)

    asset_prices_100 = asset_prices/asset_prices.iloc[0]*100

    asset_prices = asset_prices_100
    cov_matrix = calculate_cov_matrix_from_timeseries(asset_prices)
    print(f"Risk Limit = {risk_limit}")
    # Optimize portfolio weights
    optimal_weights = optimize_portfolio(cov_matrix, risk_limit, asset_prices.shape[1])
    folio_time_series = optimized_portfolio_time_series(asset_prices, optimal_weights).values
    results = {}
    results["weights"] = optimal_weights
    results["cagr"] = calculate_cagr(folio_time_series)
    results["max_drawdown"] = calculate_max_drawdown(folio_time_series)
    results["sharpe_ratio"] = calculate_sharpe_ratio(folio_time_series)
    results["portfolio_variance"] = np.sqrt(portfolio_variance(optimal_weights, calculate_cov_matrix_from_timeseries(asset_prices)))
    return results

@app.route('/get_results', methods=['POST'])
def get_results():
    try:
        # Parse the incoming form data
        print(request.form.get('assets'))
        data_raw = request.form.get('assets', '[]')
        assets_selected = ast.literal_eval(data_raw)
        risk_limit = float(request.form.get('risk_limit', 0.15))
        print(f"Assets selected: {assets_selected}")
        print(f"Risk limit: {risk_limit}")

        # Call your results function
        raw_results = results(assets_selected, risk_limit)

        # Convert any NumPy arrays or floats to Python-native types
        results_data = {
            'weights': [float(w) for w in raw_results['weights']],
            'cagr': float(raw_results['cagr']),
            'max_drawdown': float(raw_results['max_drawdown']),
            'sharpe_ratio': float(raw_results['sharpe_ratio']),
            'portfolio_variance': float(raw_results['portfolio_variance'])
        }

        return jsonify(results_data)
    
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 400


if __name__ == '__main__':
    app.run(debug=True,port=5000)