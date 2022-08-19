FROM python:3.9-slim

# Add pipenv.
RUN pip install pipenv &&\
    mkdir -p /app/gcpdiag &&\
    mkdir -p ~/.cache/gcpdiag

COPY Pipfile Pipfile.lock /app/gcpdiag/
RUN cd /app/gcpdiag &&\
    pipenv install --system &&\
    pip install flask &&\
    pip install jira &&\
    pip install gunicorn &&\
    apt-get update &&\
    apt-get install -y gunicorn

COPY . /app/gcpdiag

ENV PYTHONPATH=/app/gcpdiag
ENV SECRET=/app/gcpdiag/cloud-run-test-key/cloud-run-test-key

WORKDIR /app/gcpdiag
CMD gunicorn --workers 1 --threads 8 --timeout 0 --bind :8000 bin.wsgi:app
# CMD python3 bin/wsgi.py

EXPOSE 8000
