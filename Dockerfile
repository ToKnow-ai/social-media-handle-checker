# read the doc: https://huggingface.co/docs/hub/spaces-sdks-docker
# you will also find guides on how best to write your Dockerfile

FROM python:3.9

RUN useradd -m -u 1000 user

WORKDIR /app

COPY --chown=user ./requirements.txt requirements.txt

RUN pip install --no-cache-dir --upgrade -r requirements.txt

RUN apt-get -y update && apt-get -y install whois && apt-get -y install netbase

COPY --chown=user . /app

# CMD ["gunicorn", "-b", "0.0.0.0:7860", "app:app"]
# Use Gunicorn to run the Quart application
# https://github.com/benoitc/gunicorn/issues/2109#issuecomment-530030943
CMD ["gunicorn", "--bind", "0.0.0.0:7860", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "app:app"]
