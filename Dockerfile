FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# libgomp is required by scipy's threaded routines, which ProDy uses for the
# Hessian decomposition. The X11 libraries that used to be here were for RDKit,
# which is no longer a dependency.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY biotech_accelerator ./biotech_accelerator

# A regular install, not editable: the source is baked into the image and there
# is nothing to edit in place.
RUN pip install --upgrade pip && pip install .

# Structures are cached under the runtime user's home, so it has to be writable.
RUN useradd --create-home --uid 10001 biotech
USER biotech
ENV HOME=/home/biotech

ENTRYPOINT ["biotech"]
