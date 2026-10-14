FROM ghcr.io/astral-sh/uv:0.13.1 AS uv

FROM public.ecr.aws/lambda/python:3.14@sha256:b81a4aa3bc1d56999090333cefea611e5a84bb4e2638c1ae4107fdc9b8622da3

COPY --from=uv /uv /bin/uv

# Precompile dependencies to .pyc for faster cold starts
ENV UV_COMPILE_BYTECODE=1

# Dependency manifests only, so code changes don't invalidate this layer
# uv needs every workspace member's pyproject.toml to read the lockfile
COPY pyproject.toml uv.lock /build/
COPY services/api/pyproject.toml /build/services/api/
COPY services/batch/pyproject.toml /build/services/batch/
COPY shared/pyproject.toml /build/shared/

RUN cd /build && \
    uv export --package batch --locked --no-dev --no-emit-workspace -o requirements.txt && \
    uv pip install --no-cache -r requirements.txt --target "${LAMBDA_TASK_ROOT}" && \
    rm -rf /build

# Code last
# Least frequently changed first
COPY shared/src/shared/ ${LAMBDA_TASK_ROOT}/shared/
COPY services/batch/app/ ${LAMBDA_TASK_ROOT}/app/

CMD ["app.main.handler"]
