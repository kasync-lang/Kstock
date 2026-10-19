import json
import logging
from http import HTTPStatus

from jose import jwk
from jose.utils import base64url_encode
from app.core.config import KeyStore
from jwcrypto.jwk import JWK
from fastapi import APIRouter, HTTPException
import os
router = APIRouter(prefix="/.well-known", tags=["jwk"])


@router.get("/jwk")
def get_jwk():
    logging.warning(KeyStore.public_key)
    if not KeyStore.public_key:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="JWK not found")
    key = JWK.from_pem(KeyStore.public_key)
    jwk_data= json.loads(key.export(private_key=False))
    return {"jwk_data": jwk_data}






