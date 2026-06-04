FROM node:22.22.0-bookworm-slim@sha256:dd9d21971ec4395903fa6143c2b9267d048ae01ca6d3ea96f16cb30df6187d94

ARG DEBIAN_FRONTEND=noninteractive

LABEL org.opencontainers.image.title="Spotlight sandbox runtime"
LABEL org.opencontainers.image.description="Pinned Spotlight runtime for sandboxed agent and integration execution"

WORKDIR /opt/spotlight

COPY container/apt-packages.txt /opt/spotlight/container/apt-packages.txt
RUN apt-get update \
  && apt-get install -y --no-install-recommends $(grep -vE '^\s*(#|$)' /opt/spotlight/container/apt-packages.txt) \
  && rm -rf /var/lib/apt/lists/*

COPY container/package.json container/package-lock.json /opt/spotlight/container/
RUN cd /opt/spotlight/container && npm ci --omit=dev
ENV PATH="/opt/spotlight/container/node_modules/.bin:${PATH}"

COPY container/requirements.txt /opt/spotlight/container/requirements.txt
RUN python3 -m venv /opt/spotlight/venv \
  && /opt/spotlight/venv/bin/python -m pip install --no-cache-dir --require-hashes -r /opt/spotlight/container/requirements.txt
ENV PATH="/opt/spotlight/venv/bin:${PATH}"

WORKDIR /workspace
CMD ["bash"]
