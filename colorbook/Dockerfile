ARG BUILD_FROM
FROM ${BUILD_FROM}

ENV LANG=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps for Pillow wheels on Alpine-based base
RUN apk add --no-cache \
        libjpeg-turbo \
        zlib \
        freetype \
        tiff \
        lcms2 \
        openjpeg \
    && apk add --no-cache --virtual .build-deps \
        build-base \
        jpeg-dev \
        zlib-dev \
        freetype-dev \
        tiff-dev \
        lcms2-dev \
        openjpeg-dev

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && apk del .build-deps

COPY app/ ./app/
COPY run.sh /run.sh
RUN chmod a+x /run.sh

EXPOSE 8099

CMD [ "/run.sh" ]
