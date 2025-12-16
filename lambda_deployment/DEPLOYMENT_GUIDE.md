# Smart Sailing Route Planner - AWS Lambda Deployment

## Prerequisites

- AWS Account with Lambda access
- AWS CLI or AWS Console access
- API Gateway configured (REST API or HTTP API)

## Deployment Steps

### 1. Verify Package Contents

The `lambda_deployment_package.zip` should contain:

```
lambda_function.py
models.py
route_generator.py
route_scorer.py
isochrone_router.py
weather_fetcher.py
polars.py
python/
  requests/
  urllib3/
  certifi/
  charset_normalizer/
  idna/
```

### 2. Upload to AWS Lambda

**Via AWS Console:**

1. Go to AWS Lambda console
2. Click "Create function"
3. Choose "Author from scratch"
4. Set runtime to **Python 3.11 or higher**
5. Click "Create function"
6. Scroll to "Code source" section
7. Click "Upload from" → "Zip file"
8. Upload `lambda_deployment_package.zip`
9. Click "Save"

**Via AWS CLI:**

```bash
aws lambda create-function \
  --function-name smart-sailing-router \
  --runtime python3.11 \
  --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-execution-role \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://lambda_deployment_package.zip \
  --timeout 60 \
  --memory-size 512
```

### 3. Configure Lambda Settings

**Timeout:** 60+ seconds (route calculations with weather API calls can take time)

**Memory:** 512 MB minimum (1024 MB recommended for better performance)

**Environment Variables (Optional):**
- None required - API keys not needed (uses free Open-Meteo API)

### 4. Set up API Gateway

**Using REST API v1:**

1. Create new REST API or use existing
2. Create POST resource `/calculate-routes`
3. Enable CORS
4. Create Lambda integration pointing to your Lambda function
5. Deploy to stage

**Using HTTP API v2:**

1. Create new HTTP API or use existing
2. Create POST route `POST /calculate-routes`
3. Link to your Lambda function
4. Deploy

### 5. Test the API

**Health Check:**

```bash
curl -X GET https://YOUR_API_GATEWAY_URL/health
```

**Calculate Routes:**

```bash
curl -X POST https://YOUR_API_GATEWAY_URL/calculate-routes \
  -H "Content-Type: application/json" \
  -d '{
    "start": {"lat": 40.7128, "lng": -74.0060},
    "end": {"lat": 51.5074, "lng": -0.1278},
    "boat_type": "sailboat",
    "departure_time": "2024-12-16T10:00:00Z"
  }'
```

## API Request Format

```json
{
  "start": {
    "lat": 40.7128,
    "lng": -74.0060
  },
  "end": {
    "lat": 51.5074,
    "lng": -0.1278
  },
  "boat_type": "sailboat",
  "departure_time": "2024-12-16T10:00:00Z"
}
```

**Boat Types:** `sailboat`, `motorboat`, `catamaran`

**Departure Time:** ISO 8601 format with timezone

## API Response Format

```json
{
  "routes": [
    {
      "name": "Isochrone Route 1",
      "type": "direct",
      "score": 78,
      "distance": 3245.2,
      "estimatedTime": "12h 30m",
      "estimatedHours": 12.5,
      "waypoints": [
        {
          "position": {"lat": 40.7128, "lng": -74.0060},
          "estimatedArrival": "2024-12-16T10:00:00",
          "weather": {
            "windSpeed": 15.0,
            "windSustained": 12.0,
            "windGusts": 18.0,
            "windDirection": 180.0,
            "waveHeight": 1.5,
            "precipitation": 0.0,
            "visibility": 20.0,
            "temperature": 15.0
          }
        }
      ],
      "warnings": ["High wind expected"],
      "pros": ["Good sailing wind"],
      "cons": ["Longer route"]
    }
  ],
  "calculatedAt": "2024-12-16T10:00:00.000000"
}
```

## Monitoring & Debugging

### CloudWatch Logs

Monitor logs in CloudWatch:

1. Go to CloudWatch console
2. Click "Logs"
3. Search for `/aws/lambda/smart-sailing-router`
4. Check logs for detailed execution info

### Common Issues

**Timeout (HTTP 504):**
- Increase Lambda timeout to 60+ seconds
- Check CloudWatch logs for slow weather API calls

**Memory Error:**
- Increase Lambda memory to 512+ MB
- Memory is needed for polar diagram calculations

**No Routes Found:**
- Check if departure_time is in valid ISO 8601 format
- Verify coordinates are valid (lat: -90 to 90, lng: -180 to 180)

**Weather API Errors:**
- Open-Meteo is free and reliable, but may have rate limits
- Check CloudWatch logs for API response details
- Routes will still work with estimated weather if API fails

## Updating the Deployment

To deploy new code:

1. Make changes to backend files
2. Rebuild the zip: `./build_lambda_package.ps1` (or equivalent)
3. Upload new zip to Lambda
4. Click "Deploy" in Lambda console

## Cost Estimation

**Lambda Pricing (US East 1, as of 2024):**
- Per 1M requests: $0.20
- Per GB-second: $0.0000166667
- Free tier: 1M requests/month, 400,000 GB-seconds/month

**Example Monthly Cost (1000 requests):**
- Requests: Free (within tier)
- Duration: ~12s × 512MB × 1000 = ~96,000 GB-seconds = ~$1.60
- **Total: ~$1.60/month** (within free tier if under 1M requests)

## Support

For issues or questions:

1. Check CloudWatch logs
2. Verify request format matches documentation
3. Test weather API: https://open-meteo.com
4. Review Lambda configuration (timeout, memory)

