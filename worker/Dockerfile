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

COPY --chown=root:root \
    entrypoint.sh \
    git-askpass.sh \
    prepare-repo.sh \
    run-task.sh \
    push-repo.sh \
    capture-diff.sh \
    run-check.sh \
    /usr/local/lib/nidavelir-worker/

RUN ln -s /usr/local/lib/nidavelir-worker/entrypoint.sh /usr/local/bin/nidavelir-worker \
    && ln -s /usr/local/lib/nidavelir-worker/git-askpass.sh /usr/local/bin/nidavelir-git-askpass \
    && ln -s /usr/local/lib/nidavelir-worker/prepare-repo.sh /usr/local/bin/nidavelir-prepare \
    && ln -s /usr/local/lib/nidavelir-worker/run-task.sh /usr/local/bin/nidavelir-run-task \
    && ln -s /usr/local/lib/nidavelir-worker/push-repo.sh /usr/local/bin/nidavelir-push \
    && ln -s /usr/local/lib/nidavelir-worker/capture-diff.sh /usr/local/bin/nidavelir-capture-diff \
    && ln -s /usr/local/lib/nidavelir-worker/run-check.sh /usr/local/bin/nidavelir-run-check \
    && chmod 0555 /usr/local/lib/nidavelir-worker/*.sh

USER nidavelir
WORKDIR /workspace/repo

ENV HOME=/home/nidavelir \
    NIDAVELIR_WORKSPACE=/workspace/repo

ENTRYPOINT ["/usr/local/bin/nidavelir-worker"]
CMD ["sleep", "infinity"]
