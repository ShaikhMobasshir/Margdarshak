"""
Bunker Fuel Price Regressor (Placeholder)

This module is intended to incorporate historical Very Low Sulphur Fuel Oil (VLSFO)
prices as an additional regressor in the Prophet forecasting model. 

Currently, this is marked as a documented gap and NOT implemented, because we do not 
fabricate synthetic fuel price data to make the feature "work". This maintains the 
honesty standard applied to all other data sources in this project.

Once a real, sourced historical VLSFO price dataset is available, it should be 
placed at:
    data/raw/vlsfo_price_historical.csv

When that data is available, this module will be implemented to:
1. Load and clean the VLSFO price data.
2. Merge it with the BDI data.
3. Be wired into train_model.py to add `add_regressor('vlsfo_price')` to the model.
"""

def add_fuel_regressor(df, model):
    """
    Placeholder function for adding a bunker fuel price regressor to the model.
    
    Args:
        df (pd.DataFrame): The training dataset.
        model (Prophet): The Prophet model instance before fitting.
        
    Raises:
        NotImplementedError: Until real VLSFO data is provided.
    """
    raise NotImplementedError(
        "Bunker fuel price regressor requires real historical data at "
        "data/raw/vlsfo_price_historical.csv. Do not fabricate this data."
    )
