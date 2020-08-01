FROM python:3.6.2-jessie

RUN mkdir /code
WORKDIR /code

COPY ./requirements.txt ./

RUN apt-get update
RUN apt-get install -y xfonts-cyrillic
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

RUN cd /code
CMD ["python", "main.py"]
