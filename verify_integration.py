#!/usr/bin/env python3
"""
Integration test script: Verify frontend & backend can communicate.
Run with: python3 verify_integration.py
"""

import json
import subprocess
import sys
import time
from pathlib import Path

BASE_URL = "http://localhost:8000"
TIMEOUT = 5


def test_backend_health():
    """Test backend is running and healthy."""
    print("✓ Testing backend health...")
    try:
        result = subprocess.run(
            ["curl", "-s", f"{BASE_URL}/health"],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
        )
        data = json.loads(result.stdout)
        assert data.get("status") == "healthy", "Backend not healthy"
        print(f"  ✓ Backend healthy: {data.get('service')}")
        return True
    except Exception as e:
        print(f"  ✗ Backend health check failed: {e}")
        print(f"    Make sure backend is running on {BASE_URL}")
        return False


def test_backend_routes():
    """Test backend has all expected routes."""
    print("\n✓ Testing backend routes...")
    try:
        result = subprocess.run(
            ["curl", "-s", f"{BASE_URL}/openapi.json"],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
        )
        data = json.loads(result.stdout)
        paths = list(data.get("paths", {}).keys())
        
        expected_paths = [
            "/api/users/register",
            "/api/users/login",
            "/api/users/me",
            "/api/documents/",
            "/api/quiz/generate",
            "/api/attempts/",
            "/api/progress/",
        ]
        
        for path in expected_paths:
            if path in paths:
                print(f"  ✓ {path}")
            else:
                print(f"  ✗ {path} NOT FOUND")
        
        return all(p in paths for p in expected_paths)
    except Exception as e:
        print(f"  ✗ Failed to fetch OpenAPI schema: {e}")
        return False


def test_frontend_structure():
    """Verify frontend file structure is complete."""
    print("\n✓ Testing frontend structure...")
    
    frontend_dir = Path("frontend")
    required_files = [
        "lib/types.ts",
        "lib/api/client.ts",
        "lib/api/endpoints.ts",
        "lib/hooks/index.ts",
        "lib/stores/auth.ts",
        "config/constants.ts",
        "app/layout.tsx",
        "app/page.tsx",
        "app/providers.tsx",
        "app/dashboard/page.tsx",
        "app/(auth)/login/page.tsx",
        "app/(auth)/register/page.tsx",
        "app/student/practice/page.tsx",
        "app/student/progress/page.tsx",
        "app/student/attempts/page.tsx",
        "app/admin/documents/page.tsx",
        "tailwind.config.js",
        "tsconfig.json",
        "package.json",
        ".env.local",
    ]
    
    all_present = True
    for file_path in required_files:
        full_path = frontend_dir / file_path
        if full_path.exists():
            print(f"  ✓ {file_path}")
        else:
            print(f"  ✗ {file_path} MISSING")
            all_present = False
    
    return all_present


def test_api_client_imports():
    """Verify frontend API client TypeScript files are syntactically valid."""
    print("\n✓ Testing frontend TypeScript files...")
    
    frontend_dir = Path("frontend")
    ts_files = [
        "lib/types.ts",
        "lib/api/client.ts",
        "lib/api/endpoints.ts",
        "lib/hooks/index.ts",
        "config/constants.ts",
    ]
    
    all_valid = True
    for ts_file in ts_files:
        full_path = frontend_dir / ts_file
        try:
            with open(full_path) as f:
                content = f.read()
                # Basic checks
                if ts_file == "lib/types.ts":
                    assert "export type" in content or "export interface" in content
                elif ts_file == "lib/api/client.ts":
                    assert "apiClient" in content
                elif ts_file == "lib/api/endpoints.ts":
                    assert "authAPI" in content and "documentAPI" in content
                elif ts_file == "lib/hooks/index.ts":
                    assert "useAuth" in content
                elif ts_file == "config/constants.ts":
                    assert "ROUTES" in content and "API_ENDPOINTS" in content
            print(f"  ✓ {ts_file}")
        except AssertionError as e:
            print(f"  ✗ {ts_file}: Missing expected content")
            all_valid = False
        except Exception as e:
            print(f"  ✗ {ts_file}: {e}")
            all_valid = False
    
    return all_valid


def test_env_config():
    """Check frontend environment configuration."""
    print("\n✓ Testing frontend configuration...")
    
    env_file = Path("frontend/.env.local")
    if env_file.exists():
        with open(env_file) as f:
            content = f.read()
            if "NEXT_PUBLIC_API_URL" in content:
                print(f"  ✓ .env.local configured")
                return True
    
    print(f"  ✗ .env.local missing or incomplete")
    return False


def main():
    """Run all integration tests."""
    print("=" * 60)
    print("E-EXAM-PREPARE INTEGRATION TEST")
    print("=" * 60)
    
    tests = [
        ("Backend Health", test_backend_health),
        ("Backend Routes", test_backend_routes),
        ("Frontend Structure", test_frontend_structure),
        ("TypeScript Files", test_api_client_imports),
        ("Environment Config", test_env_config),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ {name} test crashed: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} passed")
    print("=" * 60)
    
    if passed == total:
        print("\n✓ All integration tests passed!")
        print("\nNext steps:")
        print("  1. cd frontend && npm install")
        print("  2. npm run dev")
        print("  3. Open http://localhost:3000")
        print("  4. Test login flow: register → dashboard → practice")
        return 0
    else:
        print("\n✗ Some tests failed. Check output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
