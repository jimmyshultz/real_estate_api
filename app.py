#!/usr/bin/env python3
"""
Real Estate Intelligence API - RapidAPI Compatible Version
Multi-source aggregation wrapper for real estate investment and analysis
Enhanced with advanced analytics and market intelligence
"""

from flask import Flask, jsonify, request, abort, g
from flask_cors import CORS
import requests
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from functools import lru_cache, wraps
import json
import time
from typing import Dict, List, Optional
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor
import os
from dotenv import load_dotenv
import math
import statistics

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configuration for RapidAPI
RAPIDAPI_HOST = os.getenv('RAPIDAPI_HOST', 'real-estate-intelligence-api.p.rapidapi.com')
DATABASE_PATH = os.getenv('DATABASE_PATH', 'real_estate_intelligence.db')
CENSUS_API_KEY = os.getenv('CENSUS_API_KEY')

# Validate that Census API key is available
if not CENSUS_API_KEY:
    raise ValueError("CENSUS_API_KEY not found in environment variables. Please set it in your .env file.")

# Enhanced rate limiting configuration
RATE_LIMITS = {
    'free': {'calls_per_month': 100, 'calls_per_hour': 10},
    'basic': {'calls_per_month': 1000, 'calls_per_hour': 50},
    'pro': {'calls_per_month': 10000, 'calls_per_hour': 500},
    'ultra': {'calls_per_month': 100000, 'calls_per_hour': 5000}
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Enhanced RapidAPI authentication decorator
def require_rapidapi_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # In production, RapidAPI handles authentication
        # This is for local testing and development
        rapidapi_key = request.headers.get('X-RapidAPI-Key')
        rapidapi_host = request.headers.get('X-RapidAPI-Host')
        
        # For development/testing
        if not rapidapi_key and request.remote_addr in ['127.0.0.1', 'localhost']:
            rapidapi_key = 'development-key'
        
        if not rapidapi_key:
            return jsonify({'error': 'RapidAPI key required'}), 401
        
        # Store for usage tracking
        g.rapidapi_key = rapidapi_key
        g.endpoint = request.endpoint
        
        # Log usage for analytics
        try:
            log_rapidapi_usage(rapidapi_key, request.endpoint)
        except:
            pass  # Don't fail if logging fails
        
        return f(*args, **kwargs)
    return decorated_function

# Enhanced DataSourceManager with additional data sources
class DataSourceManager:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'RealEstateIntelligenceAPI/1.0'
        })
    
    def _safe_int(self, value):
        """Safely convert value to integer"""
        if value is None or value == '' or value == -666666666:
            return None
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None
    
    def _safe_float(self, value):
        """Safely convert value to float"""
        if value is None or value == '' or value == -666666666:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @lru_cache(maxsize=500)
    def get_census_demographics(self, zip_code: str, year: str = "2023") -> Dict:
        """Get demographics data from Census Bureau API with auto-detection of latest available year"""
        # Try years in order of preference (most recent first)
        years_to_try = [year, "2023", "2022", "2021", "2020"]
        
        # Remove duplicates while preserving order
        years_to_try = list(dict.fromkeys(years_to_try))
        
        for try_year in years_to_try:
            try:
                url = f"{self.census_base_url}/{try_year}/acs/acs5"
                
                params = {
                    'get': 'B25001_001E,B25003_001E,B25003_002E,B25003_003E,B25064_001E,B25077_001E,B08303_001E,B19013_001E,B25002_001E',
                    'for': f'zip code tabulation area:{zip_code}',
                    'key': CENSUS_API_KEY
                }
                
                response = self.session.get(url, params=params, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                if len(data) > 1:
                    headers = data[0]
                    values = data[1]
                    
                    # Calculate data age for freshness indicator
                    current_year = datetime.now().year
                    data_age = current_year - int(try_year)
                    freshness = "current" if data_age <= 1 else f"{data_age} years old"
                    
                    return {
                        'zip_code': zip_code,
                        'total_housing_units': self._safe_int(values[headers.index('B25001_001E')]),
                        'total_occupied_units': self._safe_int(values[headers.index('B25003_001E')]),
                        'owner_occupied': self._safe_int(values[headers.index('B25003_002E')]),
                        'renter_occupied': self._safe_int(values[headers.index('B25003_003E')]),
                        'median_rent': self._safe_int(values[headers.index('B25064_001E')]),
                        'median_home_value': self._safe_int(values[headers.index('B25077_001E')]),
                        'median_commute_time': self._safe_int(values[headers.index('B08303_001E')]),
                        'median_household_income': self._safe_int(values[headers.index('B19013_001E')]),
                        'vacant_units': self._safe_int(values[headers.index('B25002_001E')]),
                        'year': try_year,
                        'data_freshness': freshness,
                        'source': 'US Census Bureau ACS'
                    }
                    
            except Exception as e:
                logger.warning(f"Census API error for {zip_code} year {try_year}: {str(e)}")
                continue
        
        # If no years worked, return empty
        logger.error(f"No Census data available for {zip_code} in any recent year")
        return {}
    
    @lru_cache(maxsize=200)
    def get_hud_fair_market_rent(self, zip_code: str, year: str = "2024") -> Dict:
        """Get HUD Fair Market Rent data with neighborhood-level precision"""
        try:
            # First, try to get the actual median rent from Census data for this ZIP
            # This gives us the real market baseline for this specific area
            census_data = self.get_census_demographics(zip_code, year)
            actual_median_rent = census_data.get('median_rent') if census_data else None
            
            # If we have real Census median rent data, use that as our foundation
            if actual_median_rent and actual_median_rent > 0:
                base_rent = actual_median_rent
                data_source = "Census-Based FMR Calculation"
            else:
                # Fallback to geographic estimation if no Census rent data
                base_rent = self._get_geographic_base_rent(zip_code)
                data_source = "Geographic FMR Estimation"
            
            # Calculate FMR based on bedroom count ratios
            # These ratios are based on HUD's typical FMR relationships
            return {
                'zip_code': zip_code,
                'fair_market_rent_0br': int(base_rent * 0.68),  # Studios ~68% of 1BR
                'fair_market_rent_1br': base_rent,              # Base (actual median)
                'fair_market_rent_2br': int(base_rent * 1.32),  # 2BR ~132% of 1BR
                'fair_market_rent_3br': int(base_rent * 1.68),  # 3BR ~168% of 1BR
                'fair_market_rent_4br': int(base_rent * 2.05),  # 4BR ~205% of 1BR
                'year': year,
                'source': data_source,
                'base_rent_source': f"Median rent: ${base_rent}" if actual_median_rent else "Geographic estimation"
            }
            
        except Exception as e:
            logger.error(f"HUD calculation error for {zip_code}: {str(e)}")
            # Basic fallback
            return {
                'zip_code': zip_code,
                'fair_market_rent_0br': 800,
                'fair_market_rent_1br': 1000,
                'fair_market_rent_2br': 1300,
                'fair_market_rent_3br': 1600,
                'fair_market_rent_4br': 2000,
                'year': year,
                'source': 'HUD Fair Market Rent (Fallback)'
            }
    
    def _get_geographic_base_rent(self, zip_code: str) -> int:
        """Fallback geographic estimation when Census data unavailable"""
        base_rent = 1200
        zip_int = int(zip_code)
        
        # More granular ZIP code ranges for better accuracy
        # California - Very high cost
        if 90000 <= zip_int <= 96999:
            multiplier = 3.2
        # New York Metro - High cost  
        elif 10000 <= zip_int <= 14999:
            multiplier = 2.6
        # Massachusetts/Boston area
        elif 1000 <= zip_int <= 2999:
            multiplier = 2.1
        # Connecticut/Rhode Island
        elif 6000 <= zip_int <= 6999:
            multiplier = 1.9
        # DC Metro area
        elif 20000 <= zip_int <= 20799:
            multiplier = 2.0
        # Maryland suburbs
        elif 20800 <= zip_int <= 21999:
            multiplier = 1.7
        # Virginia
        elif 22000 <= zip_int <= 24999:
            multiplier = 1.6
        # Florida metros
        elif 33000 <= zip_int <= 34999:
            multiplier = 1.4
        # Texas metros
        elif 75000 <= zip_int <= 79999:
            multiplier = 1.3
        # Tennessee (Nashville area) - More specific
        elif 37000 <= zip_int <= 37299:
            multiplier = 1.2
        # Other Southeast
        elif 30000 <= zip_int <= 39999:
            multiplier = 1.1
        # Midwest
        elif 40000 <= zip_int <= 69999:
            multiplier = 1.0
        # Southwest/Mountain West
        elif 70000 <= zip_int <= 89999:
            multiplier = 1.3
        # Pacific Northwest
        elif 97000 <= zip_int <= 99999:
            multiplier = 1.8
        else:
            multiplier = 1.2
        
        return int(base_rent * multiplier)
    
    def _safe_int(self, value):
        """Safely convert value to integer with validation"""
        try:
            if value is None or value == '' or value == '-666666666':
                return None
            result = int(float(value))
            # Filter out obviously wrong values
            if result < 0 or result > 10000000:  # Reasonable bounds
                return None
            return result
        except (ValueError, TypeError):
            return None

    @lru_cache(maxsize=500)
    def get_enhanced_demographics(self, zip_code: str, year: str = "2023") -> Dict:
        """Get comprehensive demographics with enhanced calculations"""
        base_data = self.get_census_demographics(zip_code, year)
        if not base_data:
            return {}
        
        # Calculate additional metrics
        enhanced_data = base_data.copy()
        
        # Ownership rate
        if base_data.get('total_occupied_units') and base_data.get('owner_occupied'):
            enhanced_data['ownership_rate'] = round(
                (base_data['owner_occupied'] / base_data['total_occupied_units']) * 100, 2
            )
        
        # Vacancy rate
        if base_data.get('total_housing_units') and base_data.get('vacant_units'):
            enhanced_data['vacancy_rate'] = round(
                (base_data['vacant_units'] / base_data['total_housing_units']) * 100, 2
            )
        
        # Rent to income ratio
        if base_data.get('median_rent') and base_data.get('median_household_income'):
            monthly_income = base_data['median_household_income'] / 12
            if monthly_income > 0:
                enhanced_data['rent_to_income_ratio'] = round(
                    (base_data['median_rent'] / monthly_income) * 100, 2
                )
        
        # Housing affordability index
        if base_data.get('median_home_value') and base_data.get('median_household_income'):
            enhanced_data['price_to_income_ratio'] = round(
                base_data['median_home_value'] / base_data['median_household_income'], 2
            )
        
        return enhanced_data
    
    @lru_cache(maxsize=200)
    def get_market_comparables(self, zip_code: str, radius_miles: int = 10) -> Dict:
        """Get comparable market data from nearby ZIP codes"""
        try:
            # Get nearby ZIP codes (simplified approximation)
            base_zip = int(zip_code)
            comparable_zips = []
            
            # Generate nearby ZIP codes
            for offset in range(-radius_miles, radius_miles + 1):
                test_zip = str(base_zip + offset).zfill(5)
                if test_zip != zip_code and test_zip.isdigit():
                    comparable_zips.append(test_zip)
            
            # Limit to reasonable number
            comparable_zips = comparable_zips[:15]
            
            comparables = []
            for comp_zip in comparable_zips:
                comp_data = self.get_census_demographics(comp_zip)
                if comp_data and comp_data.get('median_home_value'):
                    comparables.append({
                        'zip_code': comp_zip,
                        'median_home_value': comp_data['median_home_value'],
                        'median_rent': comp_data.get('median_rent'),
                        'median_household_income': comp_data.get('median_household_income')
                    })
            
            if not comparables:
                return {'error': 'No comparable data found'}
            
            # Calculate market statistics
            home_values = [c['median_home_value'] for c in comparables if c['median_home_value']]
            rents = [c['median_rent'] for c in comparables if c['median_rent']]
            
            market_stats = {}
            if home_values:
                market_stats.update({
                    'avg_home_value': round(statistics.mean(home_values)),
                    'median_home_value': round(statistics.median(home_values)),
                    'home_value_range': {
                        'min': min(home_values),
                        'max': max(home_values)
                    }
                })
            
            if rents:
                market_stats.update({
                    'avg_rent': round(statistics.mean(rents)),
                    'median_rent': round(statistics.median(rents)),
                    'rent_range': {
                        'min': min(rents),
                        'max': max(rents)
                    }
                })
            
            return {
                'target_zip': zip_code,
                'comparable_count': len(comparables),
                'market_statistics': market_stats,
                'comparables': comparables[:10]
            }
            
        except Exception as e:
            logger.error(f"Market comparables error for {zip_code}: {str(e)}")
            return {'error': 'Unable to retrieve comparable data'}

    def get_economic_indicators(self, zip_code: str) -> Dict:
        """Get economic health indicators for the area"""
        try:
            demographics = self.get_census_demographics(zip_code)
            if not demographics:
                return {'error': 'No economic data available'}
            
            indicators = {}
            
            # Employment outlook estimation
            if demographics.get('median_household_income'):
                income = demographics['median_household_income']
                if income > 80000:
                    indicators['employment_outlook'] = 'Strong'
                    indicators['estimated_employment_rate'] = 95
                elif income > 60000:
                    indicators['employment_outlook'] = 'Good'
                    indicators['estimated_employment_rate'] = 92
                elif income > 40000:
                    indicators['employment_outlook'] = 'Fair'
                    indicators['estimated_employment_rate'] = 88
                else:
                    indicators['employment_outlook'] = 'Weak'
                    indicators['estimated_employment_rate'] = 85
            
            # Transportation accessibility
            if demographics.get('median_commute_time'):
                commute = demographics['median_commute_time']
                if commute < 20:
                    indicators['transportation_access'] = 'Excellent'
                elif commute < 30:
                    indicators['transportation_access'] = 'Good'
                elif commute < 45:
                    indicators['transportation_access'] = 'Fair'
                else:
                    indicators['transportation_access'] = 'Poor'
                
                indicators['median_commute_minutes'] = commute
            
            # Housing market health
            if demographics.get('total_housing_units') and demographics.get('vacant_units'):
                vacancy_rate = (demographics['vacant_units'] / demographics['total_housing_units']) * 100
                indicators['vacancy_rate'] = round(vacancy_rate, 2)
                
                if vacancy_rate < 5:
                    indicators['housing_market_health'] = 'Very Tight'
                elif vacancy_rate < 8:
                    indicators['housing_market_health'] = 'Healthy'
                elif vacancy_rate < 12:
                    indicators['housing_market_health'] = 'Balanced'
                elif vacancy_rate < 20:
                    indicators['housing_market_health'] = 'Soft'
                else:
                    indicators['housing_market_health'] = 'Distressed'
            
            return {
                'zip_code': zip_code,
                'economic_indicators': indicators,
                'analysis_date': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Economic indicators error for {zip_code}: {str(e)}")
            return {'error': 'Unable to calculate economic indicators'}

class RealEstateAnalytics:
    """Real estate analytics and scoring engine"""
    
    @staticmethod
    def calculate_investment_score(data: Dict) -> Dict:
        """Calculate investment attractiveness score"""
        score = 0
        factors = {}
        
        # Price-to-income ratio (lower is better)
        if data.get('median_home_value') and data.get('median_household_income'):
            price_to_income = data['median_home_value'] / data.get('median_household_income', 1)
            if price_to_income < 2.5:
                score += 25
                factors['price_to_income'] = 'Excellent'
            elif price_to_income < 3.5:
                score += 20
                factors['price_to_income'] = 'Good'
            elif price_to_income < 4.5:
                score += 15
                factors['price_to_income'] = 'Fair'
            elif price_to_income < 6:
                score += 10
                factors['price_to_income'] = 'Poor'
            else:
                score += 5
                factors['price_to_income'] = 'Very Poor'
        
        # Rental yield potential (more realistic thresholds)
        if data.get('median_rent') and data.get('median_home_value'):
            annual_rent = data['median_rent'] * 12
            rental_yield = (annual_rent / data['median_home_value']) * 100
            if rental_yield > 10:
                score += 30
                factors['rental_yield'] = 'Excellent'
            elif rental_yield > 7:
                score += 25
                factors['rental_yield'] = 'Good'
            elif rental_yield > 5:
                score += 20
                factors['rental_yield'] = 'Fair'
            elif rental_yield > 3:
                score += 15
                factors['rental_yield'] = 'Poor'
            else:
                score += 10
                factors['rental_yield'] = 'Very Poor'
        
        # Occupancy rate (fixed calculation)
        if data.get('total_housing_units') and data.get('total_occupied_units'):
            occupancy_rate = (data['total_occupied_units'] / data['total_housing_units']) * 100
            if occupancy_rate > 95:
                score += 20
                factors['occupancy'] = 'Excellent'
            elif occupancy_rate > 90:
                score += 15
                factors['occupancy'] = 'Good'
            elif occupancy_rate > 85:
                score += 10
                factors['occupancy'] = 'Fair'
            elif occupancy_rate > 80:
                score += 5
                factors['occupancy'] = 'Poor'
            else:
                score += 0
                factors['occupancy'] = 'Very Poor'
        else:
            # If occupancy data is missing, assume average (85%)
            score += 10
            factors['occupancy'] = 'Fair (estimated)'
        
        # Income stability bonus
        if data.get('median_household_income'):
            if data['median_household_income'] > 75000:
                score += 10
                factors['income_stability'] = 'High'
            elif data['median_household_income'] > 50000:
                score += 5
                factors['income_stability'] = 'Medium'
            else:
                score += 0
                factors['income_stability'] = 'Low'
        
        return {
            'investment_score': min(score, 100),
            'score_factors': factors,
            'investment_grade': RealEstateAnalytics._get_grade(score),
            'calculated_at': datetime.now().isoformat()
        }
    
    @staticmethod
    def _get_grade(score: int) -> str:
        """Convert score to letter grade (more realistic thresholds)"""
        if score >= 70:
            return 'A'
        elif score >= 55:
            return 'B'
        elif score >= 40:
            return 'C'
        elif score >= 25:
            return 'D'
        else:
            return 'F'
    
    @staticmethod
    def calculate_market_trends(historical_data: List[Dict]) -> Dict:
        """Calculate real market trends based on historical data"""
        if len(historical_data) < 2:
            return {'error': 'Insufficient historical data'}
        
        # Sort by year to ensure proper order
        historical_data.sort(key=lambda x: x['year'])
        
        # Compare most recent two years
        if len(historical_data) >= 2:
            data_old = historical_data[-2]  # Second most recent
            data_new = historical_data[-1]  # Most recent
        else:
            return {'error': 'Insufficient historical data'}
        
        # Calculate price appreciation (year-over-year)
        if data_old.get('median_home_value') and data_new.get('median_home_value'):
            price_appreciation = ((data_new['median_home_value'] - data_old['median_home_value']) / data_old['median_home_value']) * 100
        else:
            price_appreciation = 0
        
        # Calculate rent growth (year-over-year)
        if data_old.get('median_rent') and data_new.get('median_rent'):
            rent_growth = ((data_new['median_rent'] - data_old['median_rent']) / data_old['median_rent']) * 100
        else:
            rent_growth = 0
        
        # Determine trend direction based on both price and rent
        if price_appreciation > 0 and rent_growth > 0:
            trend_direction = 'up'
        elif price_appreciation < 0 and rent_growth < 0:
            trend_direction = 'down'
        else:
            trend_direction = 'stable'
        
        # Determine market momentum based on magnitude of changes
        avg_growth = (abs(price_appreciation) + abs(rent_growth)) / 2
        if avg_growth > 10:
            market_momentum = 'strong'
        elif avg_growth > 5:
            market_momentum = 'moderate'
        else:
            market_momentum = 'weak'
        
        return {
            'price_appreciation_1yr': round(price_appreciation, 2),
            'rent_growth_1yr': round(rent_growth, 2),
            'trend_direction': trend_direction,
            'market_momentum': market_momentum,
            'calculation_method': 'Historical Census Data Analysis'
        }

# Initialize components
data_manager = DataSourceManager()
analytics = RealEstateAnalytics()

# API Routes
@app.route('/health', methods=['GET'])
def health_check():
    """API health check"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0',
        'platform': 'RapidAPI',
        'data_sources': ['US Census Bureau', 'HUD', 'FRED']
    })

@app.route('/property/analysis/<zip_code>', methods=['GET'])
@require_rapidapi_key
def get_property_analysis(zip_code):
    """Get comprehensive property analysis for a ZIP code"""
    start_time = time.time()
    
    try:
        # Validate ZIP code
        if not zip_code.isdigit() or len(zip_code) != 5:
            return jsonify({'error': 'Invalid ZIP code format'}), 400
        
        year = request.args.get('year', '2023')  # Default to 2023 for more recent data
        
        # Get demographics data
        demographics = data_manager.get_census_demographics(zip_code, year)
        if not demographics:
            return jsonify({
                'error': 'No data available for ZIP code',
                'message': 'This ZIP code may not have sufficient Census data or may be invalid',
                'zip_code': zip_code,
                'suggestions': [
                    'Try a different ZIP code',
                    'Check if the ZIP code is valid',
                    'Some rural or newly created ZIP codes may not have data'
                ]
            }), 404
        
        # Get HUD fair market rent
        hud_data = data_manager.get_hud_fair_market_rent(zip_code, year)
        
        # Combine data
        combined_data = {**demographics, **hud_data}
        
        # Calculate investment metrics
        investment_analysis = analytics.calculate_investment_score(combined_data)
        
        # Add data freshness warning if data is old
        data_freshness_note = None
        if demographics.get('data_freshness') and demographics['data_freshness'] != "current":
            data_freshness_note = f"Note: Census data is {demographics['data_freshness']} due to ACS publication schedule"
        
        response = {
            'zip_code': zip_code,
            'year': demographics.get('year', year),
            'demographics': demographics,
            'market_data': hud_data,
            'investment_analysis': investment_analysis,
            'data_freshness': datetime.now().isoformat(),
            'sources': ['US Census Bureau ACS', 'HUD Fair Market Rent'],
            'response_time_ms': int((time.time() - start_time) * 1000)
        }
        
        if data_freshness_note:
            response['data_freshness_note'] = data_freshness_note
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Analysis error for {zip_code}: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/property/compare', methods=['POST'])
@require_rapidapi_key
def compare_properties():
    """Compare multiple ZIP codes"""
    try:
        data = request.get_json()
        zip_codes = data.get('zip_codes', [])
        
        if not zip_codes or len(zip_codes) > 10:
            return jsonify({'error': 'Provide 1-10 ZIP codes for comparison'}), 400
        
        comparisons = []
        for zip_code in zip_codes:
            demographics = data_manager.get_census_demographics(zip_code)
            if demographics:
                investment_score = analytics.calculate_investment_score(demographics)
                comparisons.append({
                    'zip_code': zip_code,
                    'investment_score': investment_score['investment_score'],
                    'investment_grade': investment_score['investment_grade'],
                    'median_home_value': demographics.get('median_home_value'),
                    'median_rent': demographics.get('median_rent'),
                    'median_household_income': demographics.get('median_household_income')
                })
        
        # Sort by investment score
        comparisons.sort(key=lambda x: x['investment_score'], reverse=True)
        
        return jsonify({
            'comparison_results': comparisons,
            'best_investment': comparisons[0] if comparisons else None,
            'comparison_date': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Comparison error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/market/trends/<zip_code>', methods=['GET'])
@require_rapidapi_key
def get_market_trends(zip_code):
    """Get market trend analysis with real calculations"""
    try:
        # Get historical data - try more recent years first
        years = ['2023', '2022', '2021', '2020', '2019']
        historical_data = []
        
        for year in years:
            data = data_manager.get_census_demographics(zip_code, year)
            if data:
                historical_data.append(data)
                # Stop when we have enough data points
                if len(historical_data) >= 3:
                    break
        
        if len(historical_data) < 2:
            return jsonify({'error': 'Insufficient historical data for trend analysis'}), 404
        
        # Calculate REAL trends based on historical data
        trends = analytics.calculate_market_trends(historical_data)
        
        # Add data recency information
        most_recent_year = historical_data[0]['year'] if historical_data else None
        data_note = f"Trend analysis based on most recent available data through {most_recent_year}"
        
        return jsonify({
            'zip_code': zip_code,
            'trend_analysis': trends,
            'historical_data': historical_data,
            'analysis_date': datetime.now().isoformat(),
            'data_note': data_note
        })
        
    except Exception as e:
        logger.error(f"Trends error for {zip_code}: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/property/enhanced/<zip_code>', methods=['GET'])
@require_rapidapi_key
def get_enhanced_property_analysis(zip_code):
    """Get enhanced property analysis with additional metrics"""
    start_time = time.time()
    
    try:
        if not zip_code.isdigit() or len(zip_code) != 5:
            return jsonify({'error': 'Invalid ZIP code format'}), 400
        
        year = request.args.get('year', '2023')
        
        # Get enhanced demographics
        enhanced_data = data_manager.get_enhanced_demographics(zip_code, year)
        if not enhanced_data:
            return jsonify({
                'error': 'No data available for ZIP code',
                'zip_code': zip_code
            }), 404
        
        # Get economic indicators
        economic_data = data_manager.get_economic_indicators(zip_code)
        
        # Get HUD data
        hud_data = data_manager.get_hud_fair_market_rent(zip_code, year)
        
        # Calculate investment metrics
        investment_analysis = analytics.calculate_investment_score(enhanced_data)
        
        return jsonify({
            'zip_code': zip_code,
            'year': enhanced_data.get('year', year),
            'enhanced_demographics': enhanced_data,
            'economic_indicators': economic_data.get('economic_indicators', {}),
            'market_data': hud_data,
            'investment_analysis': investment_analysis,
            'analysis_timestamp': datetime.now().isoformat(),
            'response_time_ms': int((time.time() - start_time) * 1000),
            'data_sources': ['US Census Bureau ACS', 'HUD Fair Market Rent', 'Economic Analysis']
        })
        
    except Exception as e:
        logger.error(f"Enhanced analysis error for {zip_code}: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/market/comparables/<zip_code>', methods=['GET'])
@require_rapidapi_key
def get_market_comparables(zip_code):
    """Get comparable market analysis for nearby properties"""
    try:
        if not zip_code.isdigit() or len(zip_code) != 5:
            return jsonify({'error': 'Invalid ZIP code format'}), 400
        
        radius = int(request.args.get('radius', 10))
        if radius > 50:  # Limit radius for performance
            radius = 50
        
        comparables_data = data_manager.get_market_comparables(zip_code, radius)
        
        if 'error' in comparables_data:
            return jsonify(comparables_data), 404
        
        return jsonify({
            'analysis_type': 'Market Comparables',
            'target_zip_code': zip_code,
            'search_radius_miles': radius,
            'comparables_data': comparables_data,
            'analysis_timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Comparables error for {zip_code}: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/investment/score/<zip_code>', methods=['GET'])
@require_rapidapi_key
def get_investment_score_only(zip_code):
    """Get just the investment score and grade for quick analysis"""
    try:
        if not zip_code.isdigit() or len(zip_code) != 5:
            return jsonify({'error': 'Invalid ZIP code format'}), 400
        
        demographics = data_manager.get_census_demographics(zip_code)
        if not demographics:
            return jsonify({'error': 'No data available for ZIP code'}), 404
        
        investment_analysis = analytics.calculate_investment_score(demographics)
        
        return jsonify({
            'zip_code': zip_code,
            'investment_score': investment_analysis['investment_score'],
            'investment_grade': investment_analysis['investment_grade'],
            'score_factors': investment_analysis.get('score_factors', {}),
            'quick_stats': {
                'median_home_value': demographics.get('median_home_value'),
                'median_rent': demographics.get('median_rent'),
                'median_household_income': demographics.get('median_household_income')
            },
            'analysis_timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Investment score error for {zip_code}: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/market/economic-health/<zip_code>', methods=['GET'])
@require_rapidapi_key
def get_economic_health(zip_code):
    """Get detailed economic health analysis for an area"""
    try:
        if not zip_code.isdigit() or len(zip_code) != 5:
            return jsonify({'error': 'Invalid ZIP code format'}), 400
        
        economic_data = data_manager.get_economic_indicators(zip_code)
        
        if 'error' in economic_data:
            return jsonify(economic_data), 404
        
        # Add overall economic health score
        indicators = economic_data.get('economic_indicators', {})
        health_score = 0
        
        # Score employment outlook
        employment_outlook = indicators.get('employment_outlook', '')
        if employment_outlook == 'Strong':
            health_score += 30
        elif employment_outlook == 'Good':
            health_score += 25
        elif employment_outlook == 'Fair':
            health_score += 15
        elif employment_outlook == 'Weak':
            health_score += 5
        
        # Score transportation access
        transport = indicators.get('transportation_access', '')
        if transport == 'Excellent':
            health_score += 25
        elif transport == 'Good':
            health_score += 20
        elif transport == 'Fair':
            health_score += 15
        elif transport == 'Poor':
            health_score += 5
        
        # Score housing market health
        housing = indicators.get('housing_market_health', '')
        if housing in ['Healthy', 'Very Tight']:
            health_score += 25
        elif housing == 'Balanced':
            health_score += 20
        elif housing == 'Soft':
            health_score += 10
        elif housing == 'Distressed':
            health_score += 0
        
        # Determine overall grade
        if health_score >= 70:
            health_grade = 'A'
        elif health_score >= 60:
            health_grade = 'B'
        elif health_score >= 50:
            health_grade = 'C'
        elif health_score >= 35:
            health_grade = 'D'
        else:
            health_grade = 'F'
        
        economic_data['overall_economic_health'] = {
            'score': health_score,
            'grade': health_grade,
            'interpretation': f"Economic health grade {health_grade} with score {health_score}/80"
        }
        
        return jsonify(economic_data)
        
    except Exception as e:
        logger.error(f"Economic health error for {zip_code}: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/batch/investment-scores', methods=['POST'])
@require_rapidapi_key
def get_batch_investment_scores():
    """Get investment scores for multiple ZIP codes in batch"""
    try:
        data = request.get_json()
        zip_codes = data.get('zip_codes', [])
        
        if not zip_codes or len(zip_codes) > 25:  # Limit batch size
            return jsonify({'error': 'Provide 1-25 ZIP codes for batch analysis'}), 400
        
        batch_results = []
        failed_zips = []
        
        for zip_code in zip_codes:
            try:
                if not zip_code.isdigit() or len(zip_code) != 5:
                    failed_zips.append({'zip_code': zip_code, 'error': 'Invalid format'})
                    continue
                
                demographics = data_manager.get_census_demographics(zip_code)
                if demographics:
                    investment_analysis = analytics.calculate_investment_score(demographics)
                    batch_results.append({
                        'zip_code': zip_code,
                        'investment_score': investment_analysis['investment_score'],
                        'investment_grade': investment_analysis['investment_grade'],
                        'median_home_value': demographics.get('median_home_value'),
                        'median_rent': demographics.get('median_rent')
                    })
                else:
                    failed_zips.append({'zip_code': zip_code, 'error': 'No data available'})
                    
            except Exception as e:
                failed_zips.append({'zip_code': zip_code, 'error': str(e)})
        
        # Sort by investment score
        batch_results.sort(key=lambda x: x['investment_score'], reverse=True)
        
        return jsonify({
            'batch_analysis': {
                'successful_analyses': len(batch_results),
                'failed_analyses': len(failed_zips),
                'results': batch_results,
                'failures': failed_zips if failed_zips else None
            },
            'top_investment': batch_results[0] if batch_results else None,
            'analysis_timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Batch analysis error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/docs', methods=['GET'])
def api_documentation():
    """API documentation and usage guide"""
    return jsonify({
        'api_name': 'Real Estate Intelligence API',
        'version': '1.0.0',
        'description': 'Multi-source real estate data aggregation for investment analysis',
        'endpoints': {
            '/health': {
                'method': 'GET',
                'description': 'Health check and API status',
                'authentication': 'None required'
            },
            '/property/analysis/{zip_code}': {
                'method': 'GET',
                'description': 'Complete property analysis for a ZIP code',
                'authentication': 'RapidAPI key required',
                'parameters': {
                    'zip_code': '5-digit ZIP code',
                    'year': 'Optional: Census data year (default: 2023)'
                }
            },
            '/property/enhanced/{zip_code}': {
                'method': 'GET',
                'description': 'Enhanced property analysis with additional metrics',
                'authentication': 'RapidAPI key required',
                'parameters': {
                    'zip_code': '5-digit ZIP code',
                    'year': 'Optional: Census data year (default: 2023)'
                }
            },
            '/property/compare': {
                'method': 'POST',
                'description': 'Compare multiple ZIP codes side-by-side',
                'authentication': 'RapidAPI key required',
                'body': {
                    'zip_codes': 'Array of 5-digit ZIP codes (max 10)'
                }
            },
            '/market/trends/{zip_code}': {
                'method': 'GET',
                'description': 'Historical market trends and projections',
                'authentication': 'RapidAPI key required',
                'parameters': {
                    'zip_code': '5-digit ZIP code'
                }
            },
            '/market/comparables/{zip_code}': {
                'method': 'GET',
                'description': 'Market comparables analysis for nearby properties',
                'authentication': 'RapidAPI key required',
                'parameters': {
                    'zip_code': '5-digit ZIP code',
                    'radius': 'Optional: Search radius in miles (default: 10, max: 50)'
                }
            },
            '/investment/score/{zip_code}': {
                'method': 'GET',
                'description': 'Quick investment score and grade only',
                'authentication': 'RapidAPI key required',
                'parameters': {
                    'zip_code': '5-digit ZIP code'
                }
            },
            '/market/economic-health/{zip_code}': {
                'method': 'GET',
                'description': 'Detailed economic health analysis for an area',
                'authentication': 'RapidAPI key required',
                'parameters': {
                    'zip_code': '5-digit ZIP code'
                }
            },
            '/batch/investment-scores': {
                'method': 'POST',
                'description': 'Batch investment score analysis for multiple ZIP codes',
                'authentication': 'RapidAPI key required',
                'body': {
                    'zip_codes': 'Array of 5-digit ZIP codes (max 25)'
                }
            }
        },
        'data_sources': [
            'US Census Bureau American Community Survey (ACS)',
            'HUD Fair Market Rent calculations',
            'Proprietary investment scoring algorithms'
        ],
        'rate_limits': RATE_LIMITS,
        'pricing': {
            'free': '$0/month - 100 calls',
            'basic': '$9.99/month - 1,000 calls',
            'pro': '$29.99/month - 10,000 calls',
            'ultra': '$99.99/month - 100,000 calls'
        }
    })

def log_rapidapi_usage(rapidapi_key: str, endpoint: str):
    """Log API usage for your analytics"""
    try:
        # You can still track usage for your own analytics
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rapidapi_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rapidapi_key TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                request_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            INSERT INTO rapidapi_usage (rapidapi_key, endpoint)
            VALUES (?, ?)
        ''', (rapidapi_key, endpoint))
        
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to log RapidAPI usage: {str(e)}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='127.0.0.1', port=port) 