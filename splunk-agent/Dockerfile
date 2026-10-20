# Air-gap friendly image: build wheels on a connected host (pip wheel -r requirements.txt -w wheels/)
# and copy them in; the container itself never needs internet access.
FROM python:3.12-slim
WORKDIR /opt/splunk-agent
COPY wheels/ /tmp/wheels/
COPY requirements.txt .
RUN pip install --no-index --find-links=/tmp/wheels -r requirements.txt && rm -rf /tmp/wheels
COPY . .
RUN useradd -r -u 10001 agent && mkdir -p logs catalog && chown -R agent /opt/splunk-agent
USER agent
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "agent.py"]
CMD ["capabilities"]
