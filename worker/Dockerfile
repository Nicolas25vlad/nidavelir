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

USER nidavelir
RUN curl -fsSL https://cursor.com/install | bash
USER root

COPY --chown=root:root \
    entrypoint.sh \
    git-askpass.sh \
    prepare-repo.sh \
    run-task.sh \
    push-repo.sh \
    capture-diff.sh \
    run-check.sh \
    install-skills.sh \
    resolve-profile.sh \
    profiles.json \
    skills.lock.json \
    /usr/local/lib/nidavelir-worker/

RUN chmod 0555 /usr/local/lib/nidavelir-worker/*.sh \
    && /usr/local/lib/nidavelir-worker/install-skills.sh \
    && ln -s /usr/local/lib/nidavelir-worker/entrypoint.sh /usr/local/bin/nidavelir-worker \
    && ln -s /usr/local/lib/nidavelir-worker/git-askpass.sh /usr/local/bin/nidavelir-git-askpass \
    && ln -s /usr/local/lib/nidavelir-worker/prepare-repo.sh /usr/local/bin/nidavelir-prepare \
    && ln -s /usr/local/lib/nidavelir-worker/run-task.sh /usr/local/bin/nidavelir-run-task \
    && ln -s /usr/local/lib/nidavelir-worker/push-repo.sh /usr/local/bin/nidavelir-push \
    && ln -s /usr/local/lib/nidavelir-worker/capture-diff.sh /usr/local/bin/nidavelir-capture-diff \
    && ln -s /usr/local/lib/nidavelir-worker/run-check.sh /usr/local/bin/nidavelir-run-check \
    && ln -s /usr/local/lib/nidavelir-worker/resolve-profile.sh /usr/local/bin/nidavelir-resolve-profile

USER nidavelir
WORKDIR /workspace/repo

ENV HOME=/home/nidavelir \
    PATH=/home/nidavelir/.local/bin:$PATH \
    NIDAVELIR_WORKSPACE=/workspace/repo \
    NIDAVELIR_PROFILES_FILE=/usr/local/lib/nidavelir-worker/profiles.json \
    NIDAVELIR_SKILL_STORE=/opt/nidavelir/skill-store

ENTRYPOINT ["/usr/local/bin/nidavelir-worker"]
CMD ["sleep", "infinity"]
