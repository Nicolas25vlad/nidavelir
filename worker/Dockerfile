FROM node:22-bookworm-slim

ARG CODEX_VERSION=latest

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        jq \
        openssh-client \
        ripgrep \
    && npm install --global "@openai/codex@${CODEX_VERSION}" \
    && npm cache clean --force \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 10001 nidavelir \
    && useradd --uid 10001 --gid 10001 --create-home --shell /bin/bash nidavelir \
    && mkdir -p /workspace/repo \
    && chown -R nidavelir:nidavelir /workspace

COPY --chown=root:root entrypoint.sh /usr/local/bin/nidavelir-worker
RUN chmod 0555 /usr/local/bin/nidavelir-worker

USER nidavelir
WORKDIR /workspace/repo

ENV HOME=/home/nidavelir \
    NIDAVELIR_WORKSPACE=/workspace/repo

ENTRYPOINT ["/usr/local/bin/nidavelir-worker"]
CMD ["sleep", "infinity"]
