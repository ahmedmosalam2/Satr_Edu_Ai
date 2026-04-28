#!/bin/bash
curl -s --max-time 10 \
  -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"user_email":"admin1@satr.com","user_password":"Admin1234!"}' \
  && echo "" && echo "EXIT: $?"
