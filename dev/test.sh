
curl -i http://localhost:8081/health

curl -i http://localhost:8080/ready


curl -i -X POST http://localhost:8081/payload \
     -H "Content-Type: application/json" \
     -d '{
           "numbers": [3, 1, 4, 1, 5],
           "text": "FastAPI makes quick work of microservices."
         }'
