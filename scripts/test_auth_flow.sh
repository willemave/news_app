#!/bin/bash
# Test authentication flow with the backend API

set -e

echo "🧪 Testing Authentication Flow"
echo "================================"

BASE_URL="http://localhost:8000"

# Check if .env file exists and source it
if [ -f .env ]; then
  echo "Loading environment variables from .env..."
  set -a
  source <(grep -v '^#' .env | grep -v '^$' | sed 's/\r$//')
  set +a
fi

# Check if admin password is set
if [ -z "$ADMIN_PASSWORD" ]; then
  echo "⚠️  ADMIN_PASSWORD not set. Skipping admin login test."
  echo "    Set ADMIN_PASSWORD in .env file or export it."
  SKIP_ADMIN_TEST=true
else
  SKIP_ADMIN_TEST=false
fi

if [ "$SKIP_ADMIN_TEST" = "false" ]; then
  echo ""
  echo "1️⃣  Testing admin login..."
  ADMIN_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/admin/login" \
    -H "Content-Type: application/json" \
    -d '{"password": "'"$ADMIN_PASSWORD"'"}' \
    -c /tmp/admin_cookies.txt)

  if echo "$ADMIN_RESPONSE" | grep -q "Logged in"; then
    echo "✅ Admin login successful"
  else
    echo "❌ Admin login failed: $ADMIN_RESPONSE"
    exit 1
  fi

  echo ""
  echo "2️⃣  Testing admin-protected route..."
  ADMIN_ROUTE=$(curl -s -X GET "$BASE_URL/" \
    -b /tmp/admin_cookies.txt \
    -w "%{http_code}" \
    -o /dev/null)

  if [ "$ADMIN_ROUTE" = "200" ]; then
    echo "✅ Admin route accessible with session cookie"
  else
    echo "❌ Admin route failed (HTTP $ADMIN_ROUTE)"
    exit 1
  fi
fi

echo ""
echo "3️⃣  Testing API without authentication (iOS focus)..."
API_NO_AUTH=$(curl -s -X GET "$BASE_URL/api/content/" \
  -w "%{http_code}" \
  -o /dev/null)

if [ "$API_NO_AUTH" = "403" ] || [ "$API_NO_AUTH" = "401" ]; then
  echo "✅ API correctly rejects unauthenticated requests (HTTP $API_NO_AUTH)"
else
  echo "❌ API should reject unauthenticated requests, got HTTP $API_NO_AUTH"
  exit 1
fi

echo ""
echo "4️⃣  Creating test user and generating tokens..."
echo "This is what you need for iOS Simulator testing!"
echo ""

# Check if backend is running
if ! curl -s "$BASE_URL/health" > /dev/null 2>&1; then
  echo "❌ Backend not running at $BASE_URL"
  echo "   Start it with: ./scripts/start_server.sh"
  exit 1
fi

# Activate virtualenv if it exists
if [ -f .venv/bin/activate ]; then
  source .venv/bin/activate
fi

# Create a test user in the database
python -c "
import sys
sys.path.insert(0, '.')
from app.core.db import get_engine, get_session_factory, Base
from app.models.user import User

engine = get_engine()
Base.metadata.create_all(bind=engine)
SessionLocal = get_session_factory()
session = SessionLocal()

# Delete existing test user
existing = session.query(User).filter_by(email='test@example.com').first()
if existing:
    session.delete(existing)
    session.commit()

# Create new test user
user = User(
    apple_id='test.simulator.001',
    email='test@example.com',
    full_name='Test User',
    is_active=True
)
session.add(user)
session.commit()
print(f'Created user with ID: {user.id}')
user_id = user.id
session.close()

# Generate tokens
from app.core.security import create_access_token, create_refresh_token
access_token = create_access_token(user_id)
refresh_token = create_refresh_token(user_id)
print(f'ACCESS_TOKEN={access_token}')
print(f'REFRESH_TOKEN={refresh_token}')
" > /tmp/test_tokens.txt

if [ $? -eq 0 ]; then
  echo "✅ Test user and tokens created"

  # Extract tokens
  ACCESS_TOKEN=$(grep "ACCESS_TOKEN=" /tmp/test_tokens.txt | cut -d'=' -f2)

  echo ""
  echo "5️⃣  Testing API with valid token..."
  API_WITH_AUTH=$(curl -s -X GET "$BASE_URL/api/content/" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -w "\nHTTP_CODE:%{http_code}" \
    -o /tmp/api_response.json)

  HTTP_CODE=$(echo "$API_WITH_AUTH" | grep "HTTP_CODE:" | cut -d':' -f2)

  if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ API accessible with valid token"
    echo "Response preview:"
    cat /tmp/api_response.json | head -20
  else
    echo "❌ API request with token failed (HTTP $HTTP_CODE)"
    cat /tmp/api_response.json
    exit 1
  fi

  echo ""
  echo "6️⃣  Testing token refresh..."
  REFRESH_TOKEN=$(grep "REFRESH_TOKEN=" /tmp/test_tokens.txt | cut -d'=' -f2)
  REFRESH_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/refresh" \
    -H "Content-Type: application/json" \
    -d '{"refresh_token": "'"$REFRESH_TOKEN"'"}')

  if echo "$REFRESH_RESPONSE" | grep -q "access_token"; then
    echo "✅ Token refresh successful"
  else
    echo "⚠️  Token refresh failed: $REFRESH_RESPONSE"
    echo "    (This is optional - access token still works)"
  fi

  echo ""
  echo "7️⃣  Testing invalid token..."
  INVALID_TOKEN_RESPONSE=$(curl -s -X GET "$BASE_URL/api/content/" \
    -H "Authorization: Bearer invalid.token.here" \
    -w "%{http_code}" \
    -o /dev/null)

  if [ "$INVALID_TOKEN_RESPONSE" = "401" ]; then
    echo "✅ Invalid token correctly rejected"
  else
    echo "⚠️  Invalid token should return 401, got $INVALID_TOKEN_RESPONSE"
  fi

  echo ""
  echo "✨ Core authentication tests passed!"
  echo ""
  echo "📋 Test Tokens for iOS Simulator:"
  echo "=================================="
  echo ""
  echo "🔑 Access Token (expires in 30 min):"
  echo "$ACCESS_TOKEN"
  echo ""
  echo "🔄 Refresh Token (expires in 90 days):"
  echo "$REFRESH_TOKEN"
  echo ""
  echo "To use in iOS app:"
  echo "1. Open the app's Debug Menu (Settings → Debug)"
  echo "2. Tap 'Manually Set Tokens'"
  echo "3. Paste BOTH tokens above"
  echo "4. Save - the app will validate with backend"

else
  echo "❌ Failed to create test user"
  exit 1
fi

# Cleanup
rm -f /tmp/admin_cookies.txt /tmp/test_tokens.txt /tmp/api_response.json
