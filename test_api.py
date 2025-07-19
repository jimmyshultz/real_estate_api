#!/usr/bin/env python3
"""
Simple test script to verify Real Estate Intelligence API structure
Tests the basic API endpoints without requiring external dependencies
"""

import sys
import os

def test_api_structure():
    """Test that the API file structure is correct"""
    print("🧪 Testing API Structure...")
    
    # Check if main files exist
    required_files = [
        'app.py',
        'requirements.txt',
        'openapi.yaml',
        'vercel.json',
        'README.md',
        'RAPIDAPI_SUBMISSION_GUIDE.md'
    ]
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print(f"❌ Missing files: {missing_files}")
        return False
    else:
        print("✅ All required files present")
        return True

def test_api_imports():
    """Test that the API imports are valid"""
    print("\n🧪 Testing API Imports...")
    
    try:
        # Test basic imports that should be available
        import sys
        import os
        import json
        import time
        from datetime import datetime, timedelta
        print("✅ Basic Python imports successful")
        
        # Test if app.py can be parsed (syntax check)
        with open('app.py', 'r') as f:
            code = f.read()
            compile(code, 'app.py', 'exec')
        print("✅ app.py syntax is valid")
        
        return True
        
    except Exception as e:
        print(f"❌ Import/syntax error: {str(e)}")
        return False

def test_openapi_spec():
    """Test that OpenAPI specification is valid JSON/YAML"""
    print("\n🧪 Testing OpenAPI Specification...")
    
    try:
        with open('openapi.yaml', 'r') as f:
            content = f.read()
            
        # Basic validation - check for required sections
        required_sections = [
            'openapi: 3.0.0',
            'info:',
            'paths:',
            '/health:',
            '/property/analysis',
            '/property/enhanced',
            '/market/comparables',
            '/investment/score',
            '/batch/investment-scores'
        ]
        
        missing_sections = []
        for section in required_sections:
            if section not in content:
                missing_sections.append(section)
        
        if missing_sections:
            print(f"❌ Missing OpenAPI sections: {missing_sections}")
            return False
        else:
            print("✅ OpenAPI specification contains all required sections")
            return True
            
    except Exception as e:
        print(f"❌ OpenAPI error: {str(e)}")
        return False

def test_endpoint_definitions():
    """Test that all endpoints are properly defined in app.py"""
    print("\n🧪 Testing Endpoint Definitions...")
    
    try:
        with open('app.py', 'r') as f:
            content = f.read()
        
        # Check for all endpoint definitions
        required_endpoints = [
            "@app.route('/health'",
            "@app.route('/property/analysis/<zip_code>'",
            "@app.route('/property/enhanced/<zip_code>'",
            "@app.route('/property/compare'",
            "@app.route('/market/trends/<zip_code>'",
            "@app.route('/market/comparables/<zip_code>'",
            "@app.route('/investment/score/<zip_code>'",
            "@app.route('/market/economic-health/<zip_code>'",
            "@app.route('/batch/investment-scores'",
            "@app.route('/docs'"
        ]
        
        missing_endpoints = []
        for endpoint in required_endpoints:
            if endpoint not in content:
                missing_endpoints.append(endpoint)
        
        if missing_endpoints:
            print(f"❌ Missing endpoint definitions: {missing_endpoints}")
            return False
        else:
            print("✅ All endpoint definitions found")
            return True
            
    except Exception as e:
        print(f"❌ Endpoint definition error: {str(e)}")
        return False

def test_rapidapi_integration():
    """Test that RapidAPI integration features are present"""
    print("\n🧪 Testing RapidAPI Integration...")
    
    try:
        with open('app.py', 'r') as f:
            content = f.read()
        
        # Check for RapidAPI-specific features
        rapidapi_features = [
            "require_rapidapi_key",
            "X-RapidAPI-Key",
            "log_rapidapi_usage",
            "RATE_LIMITS",
            "rapidapi_key = request.headers.get('X-RapidAPI-Key')"
        ]
        
        missing_features = []
        for feature in rapidapi_features:
            if feature not in content:
                missing_features.append(feature)
        
        if missing_features:
            print(f"❌ Missing RapidAPI features: {missing_features}")
            return False
        else:
            print("✅ RapidAPI integration features found")
            return True
            
    except Exception as e:
        print(f"❌ RapidAPI integration error: {str(e)}")
        return False

def test_vercel_configuration():
    """Test that Vercel deployment configuration is correct"""
    print("\n🧪 Testing Vercel Configuration...")
    
    try:
        with open('vercel.json', 'r') as f:
            import json
            config = json.load(f)
        
        # Check required Vercel configuration elements
        required_elements = [
            'version',
            'functions',
            'routes'
        ]
        
        missing_elements = []
        for element in required_elements:
            if element not in config:
                missing_elements.append(element)
        
        # Check that routes cover all endpoints
        routes = config.get('routes', [])
        route_patterns = [route.get('src', '') for route in routes]
        
        required_routes = [
            '/health',
            '/property/analysis/(.*)',
            '/property/enhanced/(.*)',
            '/market/comparables/(.*)',
            '/investment/score/(.*)',
            '/batch/investment-scores'
        ]
        
        missing_routes = []
        for req_route in required_routes:
            if not any(req_route in pattern for pattern in route_patterns):
                missing_routes.append(req_route)
        
        if missing_elements:
            print(f"❌ Missing Vercel config elements: {missing_elements}")
            return False
        elif missing_routes:
            print(f"❌ Missing Vercel routes: {missing_routes}")
            return False
        else:
            print("✅ Vercel configuration is complete")
            return True
            
    except Exception as e:
        print(f"❌ Vercel configuration error: {str(e)}")
        return False

def main():
    """Run all tests"""
    print("🚀 Real Estate Intelligence API - Test Suite")
    print("=" * 50)
    
    tests = [
        test_api_structure,
        test_api_imports,
        test_openapi_spec,
        test_endpoint_definitions,
        test_rapidapi_integration,
        test_vercel_configuration
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! API is ready for RapidAPI deployment.")
        print("\n📋 Next Steps:")
        print("1. Get a Census API key: https://api.census.gov/data/key_signup.html")
        print("2. Deploy to Vercel: vercel --prod")
        print("3. Submit to RapidAPI using RAPIDAPI_SUBMISSION_GUIDE.md")
        return True
    else:
        print("❌ Some tests failed. Please fix the issues before deploying.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)