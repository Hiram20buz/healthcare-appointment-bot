# dentist-appointment-bot
An AI-powered appointment scheduling chatbot for dental clinics.

### Docker Setup

```bash
docker-compose up -d
```

### Testing the API

```bash
curl -X POST http://localhost:8000/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "Hola, ¿quién eres?"'
```
