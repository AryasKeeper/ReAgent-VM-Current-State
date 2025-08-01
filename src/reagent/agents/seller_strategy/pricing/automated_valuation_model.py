"""
Automated Valuation Model (AVM) 

Machine Learning-based property valuation using ensemble methods
with feature engineering and model validation.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from decimal import Decimal
import logging
import pickle
import asyncio
from pathlib import Path

from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import joblib

from sqlalchemy import and_, func, text
from sqlalchemy.orm import Session

from src.core.database.dependencies import get_db_session
from src.data.models.property_models import Property, PropertyPriceHistory
from src.data.models.market_models import MarketTrend, SuburbStats


@dataclass
class AVMPrediction:
    """AVM prediction result with confidence metrics."""
    property_id: str
    predicted_value: Decimal
    confidence_score: float
    prediction_interval_low: Decimal
    prediction_interval_high: Decimal
    feature_importance: Dict[str, float]
    model_accuracy: float
    market_segment: str
    prediction_date: datetime
    methodology_notes: str


@dataclass
class ModelPerformance:
    """Model performance metrics."""
    mae: float  # Mean Absolute Error
    rmse: float  # Root Mean Square Error
    mape: float  # Mean Absolute Percentage Error
    r2_score: float  # R-squared
    cross_val_score: float
    training_samples: int
    last_trained: datetime


class AutomatedValuationModel:
    """
    Advanced Automated Valuation Model using ensemble machine learning.
    
    Features:
    - Random Forest, Gradient Boosting, and Linear regression ensemble
    - Comprehensive feature engineering including location, property, and market features
    - Cross-validation and performance tracking
    - Confidence interval prediction
    - Regular model retraining and validation
    """
    
    def __init__(self, model_cache_dir: str = "/tmp/reagent_avm_models"):
        self.logger = logging.getLogger(__name__)
        self.model_cache_dir = Path(model_cache_dir)
        self.model_cache_dir.mkdir(exist_ok=True)
        
        # Model components
        self.models = {}
        self.scalers = {}
        self.encoders = {}
        self.feature_importance = {}
        self.performance_metrics = {}
        
        # Model parameters
        self.min_training_samples = 100
        self.max_model_age_days = 30
        self.test_size = 0.2
        self.cv_folds = 5
        
        # Feature lists
        self.numeric_features = [
            'bedrooms', 'bathrooms', 'car_spaces', 'land_size', 'building_size',
            'latitude', 'longitude', 'days_on_market',
            'suburb_median_price', 'suburb_price_growth', 'market_activity_score'
        ]
        
        self.categorical_features = [
            'property_type', 'suburb', 'postcode'
        ]
        
        # Market segments for specialized models
        self.market_segments = {
            'budget': (0, 1000000),
            'mid_range': (1000000, 2000000),
            'premium': (2000000, 5000000),
            'luxury': (5000000, float('inf'))
        }
    
    async def predict_value(
        self, 
        property_data: Dict[str, Any],
        include_confidence: bool = True
    ) -> AVMPrediction:
        """
        Predict property value using trained ML models.
        
        Args:
            property_data: Property features dictionary
            include_confidence: Whether to calculate confidence intervals
            
        Returns:
            AVMPrediction with value estimate and confidence metrics
        """
        try:
            self.logger.info(f"Predicting value for property {property_data.get('id')}")
            
            # Prepare features
            features = await self._prepare_features(property_data)
            
            # Determine market segment
            market_segment = self._determine_market_segment(property_data)
            
            # Load or train model for this segment
            model_key = f"avm_{market_segment}"
            if not await self._is_model_valid(model_key):
                await self._train_model(market_segment)
            
            # Make prediction
            prediction, confidence = await self._predict_with_ensemble(
                features, market_segment, include_confidence
            )
            
            # Get feature importance
            feature_importance = self.feature_importance.get(model_key, {})
            
            # Calculate prediction intervals if requested
            interval_low, interval_high = None, None
            if include_confidence:
                interval_low, interval_high = self._calculate_prediction_intervals(
                    prediction, confidence, market_segment
                )
            
            result = AVMPrediction(
                property_id=property_data.get('id', 'unknown'),
                predicted_value=Decimal(str(round(prediction, 2))),
                confidence_score=confidence,
                prediction_interval_low=Decimal(str(round(interval_low, 2))) if interval_low else None,
                prediction_interval_high=Decimal(str(round(interval_high, 2))) if interval_high else None,
                feature_importance=feature_importance,
                model_accuracy=self.performance_metrics.get(model_key, {}).get('r2_score', 0.0),
                market_segment=market_segment,
                prediction_date=datetime.utcnow(),
                methodology_notes=self._generate_methodology_notes(market_segment)
            )
            
            self.logger.info(f"AVM prediction: ${prediction:,.2f} (confidence: {confidence:.2f})")
            return result
            
        except Exception as e:
            self.logger.error(f"AVM prediction failed: {str(e)}")
            raise
    
    async def train_model(self, market_segment: str = None) -> ModelPerformance:
        """
        Train or retrain the AVM for specified market segment.
        
        Args:
            market_segment: Market segment to train ('budget', 'mid_range', 'premium', 'luxury')
                          If None, trains all segments
            
        Returns:
            ModelPerformance metrics
        """
        try:
            if market_segment:
                return await self._train_model(market_segment)
            else:
                # Train all segments
                performances = {}
                for segment in self.market_segments.keys():
                    performances[segment] = await self._train_model(segment)
                
                # Return average performance
                avg_performance = ModelPerformance(
                    mae=np.mean([p.mae for p in performances.values()]),
                    rmse=np.mean([p.rmse for p in performances.values()]),
                    mape=np.mean([p.mape for p in performances.values()]),
                    r2_score=np.mean([p.r2_score for p in performances.values()]),
                    cross_val_score=np.mean([p.cross_val_score for p in performances.values()]),
                    training_samples=sum([p.training_samples for p in performances.values()]),
                    last_trained=datetime.utcnow()
                )
                
                return avg_performance
                
        except Exception as e:
            self.logger.error(f"Model training failed: {str(e)}")
            raise
    
    async def _train_model(self, market_segment: str) -> ModelPerformance:
        """Train model for specific market segment."""
        
        self.logger.info(f"Training AVM model for {market_segment} segment")
        
        # Load training data
        X, y = await self._load_training_data(market_segment)
        
        if len(X) < self.min_training_samples:
            raise ValueError(f"Insufficient training data for {market_segment}: {len(X)} samples")
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=self.test_size, random_state=42
        )
        
        # Feature scaling
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # Train ensemble models
        models = {
            'rf': RandomForestRegressor(
                n_estimators=100,
                max_depth=20,
                min_samples_split=5,
                min_samples_leaf=2,
                random_state=42,
                n_jobs=-1
            ),
            'gbm': GradientBoostingRegressor(
                n_estimators=100,
                max_depth=8,
                learning_rate=0.1,
                min_samples_split=5,
                min_samples_leaf=2,
                random_state=42
            ),
            'ridge': Ridge(alpha=1.0)
        }
        
        # Train models
        trained_models = {}
        predictions = {}
        
        for name, model in models.items():
            if name == 'ridge':
                model.fit(X_train_scaled, y_train)
                predictions[name] = model.predict(X_test_scaled)
            else:
                model.fit(X_train, y_train)
                predictions[name] = model.predict(X_test)
            
            trained_models[name] = model
        
        # Create ensemble prediction (weighted average)
        weights = {'rf': 0.4, 'gbm': 0.4, 'ridge': 0.2}
        ensemble_pred = sum(weights[name] * pred for name, pred in predictions.items())
        
        # Calculate performance metrics
        mae = mean_absolute_error(y_test, ensemble_pred)
        rmse = np.sqrt(mean_squared_error(y_test, ensemble_pred))
        mape = np.mean(np.abs((y_test - ensemble_pred) / y_test)) * 100
        r2 = r2_score(y_test, ensemble_pred)
        
        # Cross-validation score
        cv_scores = cross_val_score(
            trained_models['rf'], X_train, y_train, 
            cv=self.cv_folds, scoring='r2'
        )
        cv_score = np.mean(cv_scores)
        
        # Feature importance (from Random Forest)
        feature_names = self.numeric_features + [f"{cat}_encoded" for cat in self.categorical_features]
        importance_dict = dict(zip(
            feature_names[:len(trained_models['rf'].feature_importances_)],
            trained_models['rf'].feature_importances_
        ))
        
        # Store models and metadata
        model_key = f"avm_{market_segment}"
        self.models[model_key] = trained_models
        self.scalers[model_key] = scaler
        self.feature_importance[model_key] = importance_dict
        
        performance = ModelPerformance(
            mae=mae,
            rmse=rmse,
            mape=mape,
            r2_score=r2,
            cross_val_score=cv_score,
            training_samples=len(X),
            last_trained=datetime.utcnow()
        )
        
        self.performance_metrics[model_key] = performance
        
        # Save models to disk
        await self._save_models(model_key)
        
        self.logger.info(f"Model training completed for {market_segment} - R²: {r2:.3f}, MAE: ${mae:,.0f}")
        return performance
    
    async def _load_training_data(self, market_segment: str) -> Tuple[pd.DataFrame, np.ndarray]:
        """Load and prepare training data for the specified market segment."""
        
        # Get price range for segment
        min_price, max_price = self.market_segments[market_segment]
        
        async with get_db_session() as session:
            # Query sold properties with price history
            query = """
            SELECT 
                p.id, p.property_type, p.suburb, p.postcode,
                p.bedrooms, p.bathrooms, p.car_spaces, 
                p.land_size, p.building_size,
                p.latitude, p.longitude, p.days_on_market,
                ph.price as sale_price,
                ph.created_at as sale_date
            FROM properties p
            JOIN property_price_history ph ON p.id = ph.property_id
            WHERE ph.price_type = 'sold'
            AND ph.price BETWEEN :min_price AND :max_price
            AND ph.created_at >= :cutoff_date
            AND p.latitude IS NOT NULL 
            AND p.longitude IS NOT NULL
            AND p.bedrooms IS NOT NULL
            AND p.bathrooms IS NOT NULL
            ORDER BY ph.created_at DESC
            """
            
            cutoff_date = datetime.utcnow() - timedelta(days=365 * 2)  # 2 years of data
            
            result = await session.execute(
                text(query), 
                {
                    'min_price': min_price,
                    'max_price': max_price,
                    'cutoff_date': cutoff_date
                }
            )
            
            rows = result.fetchall()
            
            if not rows:
                raise ValueError(f"No training data found for {market_segment} segment")
            
            # Convert to DataFrame
            df = pd.DataFrame(rows, columns=[
                'id', 'property_type', 'suburb', 'postcode',
                'bedrooms', 'bathrooms', 'car_spaces',
                'land_size', 'building_size', 'latitude', 'longitude',
                'days_on_market', 'sale_price', 'sale_date'
            ])
            
            # Add market features
            df = await self._add_market_features(df)
            
            # Prepare features
            X = await self._prepare_features_dataframe(df)
            y = df['sale_price'].values
            
            return X, y
    
    async def _add_market_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add market-level features to the dataset."""
        
        # Add suburb-level statistics
        async with get_db_session() as session:
            suburb_stats = {}
            
            for suburb in df['suburb'].unique():
                stats = session.query(SuburbStats).filter(
                    SuburbStats.suburb_name == suburb
                ).order_by(SuburbStats.stats_date.desc()).first()
                
                if stats:
                    suburb_stats[suburb] = {
                        'median_price': float(stats.house_median_price or 0),
                        'price_growth': float(stats.house_price_growth_12m or 0),
                        'activity_score': min(100, (stats.sales_last_30d or 0) * 10)
                    }
                else:
                    suburb_stats[suburb] = {
                        'median_price': df[df['suburb'] == suburb]['sale_price'].median(),
                        'price_growth': 0,
                        'activity_score': 50
                    }
            
            # Map suburb features to dataframe
            df['suburb_median_price'] = df['suburb'].map(
                lambda x: suburb_stats.get(x, {}).get('median_price', 0)
            )
            df['suburb_price_growth'] = df['suburb'].map(
                lambda x: suburb_stats.get(x, {}).get('price_growth', 0)
            )
            df['market_activity_score'] = df['suburb'].map(
                lambda x: suburb_stats.get(x, {}).get('activity_score', 50)
            )
        
        return df
    
    async def _prepare_features(self, property_data: Dict[str, Any]) -> pd.DataFrame:
        """Prepare features for a single property prediction."""
        
        # Create base feature dictionary
        features = {}
        
        # Numeric features
        for feature in self.numeric_features:
            if feature in ['suburb_median_price', 'suburb_price_growth', 'market_activity_score']:
                # These will be added later
                continue
            features[feature] = property_data.get(feature, 0)
        
        # Add market features
        suburb = property_data.get('suburb')
        if suburb:
            async with get_db_session() as session:
                stats = session.query(SuburbStats).filter(
                    SuburbStats.suburb_name == suburb
                ).order_by(SuburbStats.stats_date.desc()).first()
                
                if stats:
                    features['suburb_median_price'] = float(stats.house_median_price or 0)
                    features['suburb_price_growth'] = float(stats.house_price_growth_12m or 0)
                    features['market_activity_score'] = min(100, (stats.sales_last_30d or 0) * 10)
                else:
                    features['suburb_median_price'] = 0
                    features['suburb_price_growth'] = 0
                    features['market_activity_score'] = 50
        
        # Categorical features (will be encoded)
        for feature in self.categorical_features:
            features[feature] = property_data.get(feature, 'unknown')
        
        # Convert to DataFrame
        df = pd.DataFrame([features])
        
        return await self._prepare_features_dataframe(df)
    
    async def _prepare_features_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare features DataFrame for model input."""
        
        # Handle missing values
        df = df.fillna(0)
        
        # Encode categorical features
        for feature in self.categorical_features:
            if feature in df.columns:
                # Simple label encoding (in production, use proper encoders)
                unique_values = df[feature].unique()
                encoder_dict = {val: idx for idx, val in enumerate(unique_values)}
                df[f"{feature}_encoded"] = df[feature].map(encoder_dict)
        
        # Select only numeric features for model input
        feature_columns = self.numeric_features + [f"{cat}_encoded" for cat in self.categorical_features]
        available_columns = [col for col in feature_columns if col in df.columns]
        
        return df[available_columns]
    
    async def _predict_with_ensemble(
        self, 
        features: pd.DataFrame,
        market_segment: str,
        include_confidence: bool
    ) -> Tuple[float, float]:
        """Make prediction using ensemble models."""
        
        model_key = f"avm_{market_segment}"
        models = self.models[model_key]
        scaler = self.scalers[model_key]
        
        # Scale features for ridge regression
        features_scaled = scaler.transform(features)
        
        # Get predictions from each model
        predictions = {}
        predictions['rf'] = models['rf'].predict(features)[0]
        predictions['gbm'] = models['gbm'].predict(features)[0]
        predictions['ridge'] = models['ridge'].predict(features_scaled)[0]
        
        # Ensemble prediction (weighted average)
        weights = {'rf': 0.4, 'gbm': 0.4, 'ridge': 0.2}
        ensemble_pred = sum(weights[name] * pred for name, pred in predictions.items())
        
        # Calculate confidence based on prediction consistency
        pred_values = list(predictions.values())
        prediction_std = np.std(pred_values)
        prediction_mean = np.mean(pred_values)
        
        # Confidence score (lower variation = higher confidence)
        confidence = max(0.5, 1.0 - (prediction_std / prediction_mean) if prediction_mean > 0 else 0.5)
        
        return ensemble_pred, confidence
    
    def _calculate_prediction_intervals(
        self, 
        prediction: float,
        confidence: float,
        market_segment: str
    ) -> Tuple[float, float]:
        """Calculate prediction intervals based on model performance."""
        
        model_key = f"avm_{market_segment}"
        performance = self.performance_metrics.get(model_key)
        
        if not performance:
            # Default intervals if no performance data
            margin = prediction * 0.15  # ±15%
            return prediction - margin, prediction + margin
        
        # Use model RMSE to calculate intervals
        margin = performance.rmse * 2 * (1 - confidence)  # Adjust margin by confidence
        
        return max(0, prediction - margin), prediction + margin
    
    def _determine_market_segment(self, property_data: Dict[str, Any]) -> str:
        """Determine market segment based on property characteristics."""
        
        # Use estimated price if available, otherwise use property features
        estimated_price = property_data.get('estimated_price')
        
        if not estimated_price:
            # Rough estimation based on bedrooms and suburb
            bedrooms = property_data.get('bedrooms', 3)
            suburb = property_data.get('suburb', '').lower()
            
            # Premium suburbs (simplified list)
            premium_suburbs = ['mosman', 'vaucluse', 'bellevue hill', 'point piper', 'woollahra']
            
            if suburb in premium_suburbs:
                estimated_price = bedrooms * 800000
            else:
                estimated_price = bedrooms * 400000
        
        # Determine segment
        for segment, (min_price, max_price) in self.market_segments.items():
            if min_price <= estimated_price < max_price:
                return segment
        
        return 'luxury'  # Default for very high prices
    
    async def _is_model_valid(self, model_key: str) -> bool:
        """Check if model exists and is not too old."""
        
        if model_key not in self.models:
            return False
        
        performance = self.performance_metrics.get(model_key)
        if not performance:
            return False
        
        # Check if model is too old
        age_days = (datetime.utcnow() - performance.last_trained).days
        return age_days <= self.max_model_age_days
    
    async def _save_models(self, model_key: str) -> None:
        """Save trained models to disk."""
        
        try:
            model_file = self.model_cache_dir / f"{model_key}.pkl"
            
            model_data = {
                'models': self.models[model_key],
                'scaler': self.scalers[model_key],
                'feature_importance': self.feature_importance[model_key],
                'performance': self.performance_metrics[model_key]
            }
            
            with open(model_file, 'wb') as f:
                pickle.dump(model_data, f)
                
            self.logger.info(f"Model {model_key} saved to {model_file}")
            
        except Exception as e:
            self.logger.warning(f"Failed to save model {model_key}: {e}")
    
    async def _load_models(self, model_key: str) -> bool:
        """Load trained models from disk."""
        
        try:
            model_file = self.model_cache_dir / f"{model_key}.pkl"
            
            if not model_file.exists():
                return False
            
            with open(model_file, 'rb') as f:
                model_data = pickle.load(f)
            
            self.models[model_key] = model_data['models']
            self.scalers[model_key] = model_data['scaler']
            self.feature_importance[model_key] = model_data['feature_importance']
            self.performance_metrics[model_key] = model_data['performance']
            
            self.logger.info(f"Model {model_key} loaded from {model_file}")
            return True
            
        except Exception as e:
            self.logger.warning(f"Failed to load model {model_key}: {e}")
            return False
    
    def _generate_methodology_notes(self, market_segment: str) -> str:
        """Generate methodology explanation for the AVM."""
        
        model_key = f"avm_{market_segment}"
        performance = self.performance_metrics.get(model_key)
        
        if performance:
            return (
                f"Automated Valuation Model using Random Forest, Gradient Boosting, and "
                f"Ridge Regression ensemble for {market_segment} market segment. "
                f"Model trained on {performance.training_samples} recent sales with "
                f"R² score of {performance.r2_score:.3f} and MAPE of {performance.mape:.1f}%. "
                f"Features include property characteristics, location factors, and "
                f"market conditions with cross-validation accuracy of {performance.cross_val_score:.3f}."
            )
        else:
            return (
                f"Automated Valuation Model using ensemble machine learning methods "
                f"for {market_segment} market segment. Model incorporates property "
                f"features, location premiums, and current market conditions."
            )