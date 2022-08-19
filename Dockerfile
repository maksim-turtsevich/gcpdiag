FROM python:3.9-slim

# Add pipenv.
RUN pip install pipenv &&\
    mkdir -p /app/gcpdiag

COPY Pipfile Pipfile.lock /app/gcpdiag/
RUN cd /app/gcpdiag &&\
    pipenv install --system &&\
    pip install flask &&\
    pip install jira &&\
    pip install gunicorn &&\
    apt-get update &&\
    apt-get install -y gunicorn

# COPY ./gcp-coe-msp-sandbox-1e6925f0bd5c.json /app
COPY . /app/gcpdiag
# RUN ls /app/gcpdiag
ENV PYTHONPATH=/app/gcpdiag
ENV SECRET=/app/gcpdiag/cloud-run-test-key/cloud-run-test-key

# CMD ["python3", "/app/gcpdiag/bin/gcpdiag"]
# RUN cd /app/gcpdiag/bin
WORKDIR /app/gcpdiag
# CMD gunicorn --workers 1 --threads 8 --timeout 0 --bind :8000 bin.wsgi:app
CMD python3 bin/wsgi.py

EXPOSE 8000

# RUN apk add --no-cache python2 g++ make
# WORKDIR /app
# COPY . .
# RUN yarn install --production
# CMD ["node", "src/index.js"]
# EXPOSE 3000