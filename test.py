import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import TimeSeriesSplit, cross_val_score, GridSearchCV
from sklearn.preprocessing import StandardScaler
from hoopstats import PlayerScraper
from tqdm import tqdm
import time

# Initialize scraper
player_scraper = PlayerScraper(first_name="Luka", last_name="Doncic")

# Fetch data for multiple years
years = range(2019, 2025)
all_data = pd.DataFrame()

print("Fetching data for multiple years...")
for year in tqdm(years, desc="Fetching Data"):
    season_data = player_scraper.get_game_log_by_year(year)
    if season_data is not None:
        season_data['Year'] = year
        all_data = pd.concat([all_data, pd.DataFrame(season_data)], ignore_index=True)

print("Data fetching complete.")
time.sleep(1)

# Check the first few rows of the data
print("First few rows of the data:")
print(all_data.head())

# Convert columns to correct data types
print("Converting columns to correct data types...")
all_data['PTS'] = pd.to_numeric(all_data['PTS'], errors='coerce').fillna(0)
all_data['AST'] = pd.to_numeric(all_data['AST'], errors='coerce').fillna(0)
all_data['REB'] = pd.to_numeric(all_data['TRB'], errors='coerce').fillna(0)  # Ensure TRB is used correctly
all_data['FG%'] = pd.to_numeric(all_data['FG%'], errors='coerce').fillna(0)
all_data.fillna(0, inplace=True)

# One-hot encoding for opponent
print("Encoding categorical data...")
all_data = pd.get_dummies(all_data, columns=['Opp'], drop_first=True)

# Feature Engineering: Moving average of the last 5 games for points scored, assists, and rebounds
print("Calculating rolling averages...")
all_data['rolling_avg_points_5'] = all_data['PTS'].rolling(window=5).mean().shift(1)
all_data['rolling_avg_assists_5'] = all_data['AST'].rolling(window=5).mean().shift(1)
all_data['rolling_avg_rebounds_5'] = all_data['REB'].rolling(window=5).mean().shift(1)

# Drop rows with NaNs generated by rolling calculations
print("Dropping rows with NaNs generated by rolling calculations...")
all_data.dropna(subset=['rolling_avg_points_5', 'rolling_avg_assists_5', 'rolling_avg_rebounds_5'], inplace=True)

# Check the shape of the data after processing
print("Data shape after processing:", all_data.shape)

# Prepare features and target for each model
features = ['rolling_avg_points_5', 'rolling_avg_assists_5', 'rolling_avg_rebounds_5', 'FG%'] + \
            [col for col in all_data.columns if 'Opp_' in col]  # Include one-hot encoded opponent features
targets = ['PTS', 'AST', 'REB']
models = {}

# Scale features
scaler = StandardScaler()
X = scaler.fit_transform(all_data[features])

# Check the mean and std of features after scaling
print("Feature scaling - Mean:", X.mean(axis=0), "Std:", X.std(axis=0))

# Train models for each target
for target in targets:
    y = all_data[target].values
    
    print(f"Training model for {target}...")

    # Set up time-series cross-validation
    tscv = TimeSeriesSplit(n_splits=5)
    model = RandomForestRegressor(random_state=42)

    # Use GridSearchCV for hyperparameter tuning
    param_grid = {
        'n_estimators': [100, 200],
        'max_depth': [None, 10, 20],
        'min_samples_split': [2, 5, 10],
    }
    grid_search = GridSearchCV(model, param_grid, cv=tscv, scoring='neg_mean_squared_error', n_jobs=-1)
    
    # Fit the model and track progress
    grid_search.fit(X, y)
    models[target] = grid_search.best_estimator_  # Get the best model

    # Check cross-validation scores
    scores = cross_val_score(models[target], X, y, cv=tscv, scoring='neg_mean_squared_error')
    print(f"Cross-Validation MSE for {target}: {-scores.mean():.2f}")

print("Model training complete.")

# Predict PTS, AST, REB for the upcoming game
upcoming_opponent = 'LAL'  # Replace with desired team abbreviation
upcoming_game = pd.DataFrame({
    'rolling_avg_points_5': [all_data['rolling_avg_points_5'].iloc[-1]],
    'rolling_avg_assists_5': [all_data['rolling_avg_assists_5'].iloc[-1]],
    'rolling_avg_rebounds_5': [all_data['rolling_avg_rebounds_5'].iloc[-1]],
    'FG%': [all_data['FG%'].iloc[-1]]
})

# Include one-hot encoding for the opponent
for col in all_data.columns:
    if col.startswith('Opp_'):
        upcoming_game[col] = 0  # Initialize opponent columns to 0
upcoming_game[f'Opp_{upcoming_opponent}'] = 1  # Set the upcoming opponent to 1

# Scale the upcoming game data
upcoming_game_scaled = scaler.transform(upcoming_game)

# Predict using the trained models
print(f"Making predictions for the upcoming game against {upcoming_opponent}...")
predicted_values = {target: models[target].predict(upcoming_game_scaled)[0] for target in targets}

print(f"\nPredicted values for the upcoming game against {upcoming_opponent}:")
print(f"Points: {predicted_values['PTS']:.2f}")
print(f"Assists: {predicted_values['AST']:.2f}")
print(f"Rebounds: {predicted_values['REB']:.2f}")
