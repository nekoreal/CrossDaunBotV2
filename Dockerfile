FROM python:3.12

ENV PYTHONUNBUFFERED=1

WORKDIR /CrossDaunApp

COPY req.txt .
RUN  pip install --no-cache-dir -r req.txt 

COPY . .

CMD ["python", "main.py"]
