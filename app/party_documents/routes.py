# Vendor/Customer document upload (spec §10.4). Ek hi shared blueprint — dono
# Vendor aur Customer View panel isi set of routes ko "vendor"/"customer" party_type
# ke saath call karte hain, taaki upload/list/delete/download logic ek hi jagah ho.

import os
from datetime import datetime

from flask import Blueprint, abort, current_app, jsonify, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Customer, PartyDocument, Vendor

party_documents_bp = Blueprint("party_documents", __name__)

ALLOWED_DOCUMENT_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}
MAX_DOCUMENT_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB, spec ki limit

# party_type URL me jo bhi aaye, sirf inhi do values allow karo — warna koi bhi
# random string party_type bana ke apna folder bana sakta tha.
PARTY_MODELS = {
    "vendor": Vendor,
    "customer": Customer,
}


def _allowed_document_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_DOCUMENT_EXTENSIONS


def _get_party_or_none(party_type, party_id):
    model = PARTY_MODELS.get(party_type)
    if not model:
        return None
    return model.query.filter_by(id=party_id, is_deleted=False).first()


@party_documents_bp.route("/party_documents/<party_type>/<int:party_id>")
def party_documents_list(party_type, party_id):
    if party_type not in PARTY_MODELS:
        return jsonify(documents=[]), 404
    if not _get_party_or_none(party_type, party_id):
        return jsonify(documents=[]), 404

    docs = PartyDocument.query.filter_by(
        party_type=party_type, party_id=party_id, is_deleted=False
    ).order_by(PartyDocument.uploaded_at.desc()).all()

    return jsonify(documents=[
        {
            "id": d.id,
            "title": d.document_title or d.file_name,
            "file_name": d.file_name,
            "size_kb": round((d.file_size or 0) / 1024, 1),
            "uploaded_at": d.uploaded_at.strftime("%d-%b-%Y %H:%M") if d.uploaded_at else "",
            "url": url_for("party_documents.party_documents_file", doc_id=d.id),
        }
        for d in docs
    ])


@party_documents_bp.route("/party_documents/<party_type>/<int:party_id>/add", methods=["POST"])
def party_documents_add(party_type, party_id):
    if party_type not in PARTY_MODELS:
        return jsonify(success=False, error="Unknown party type."), 404

    party = _get_party_or_none(party_type, party_id)
    if not party:
        return jsonify(success=False, error="Record not found."), 404

    file = request.files.get("document_file")
    title = (request.form.get("document_title") or "").strip()

    if not file or not file.filename:
        return jsonify(success=False, error="Please choose a file.")

    if not _allowed_document_file(file.filename):
        return jsonify(success=False, error="File must be PDF, PNG or JPG.")

    # Size check — stream ke end tak seek karke position padho, phir wapas 0 pe
    file.stream.seek(0, os.SEEK_END)
    size = file.stream.tell()
    file.stream.seek(0)
    if size > MAX_DOCUMENT_SIZE_BYTES:
        return jsonify(success=False, error="File is larger than 5 MB.")

    safe_name = secure_filename(file.filename)
    stamped_name = datetime.utcnow().strftime("%Y%m%d%H%M%S") + "_" + safe_name

    folder_name = party_type + "s"  # "vendors" / "customers"
    folder = os.path.join(current_app.config["UPLOAD_FOLDER"], folder_name, str(party_id))
    os.makedirs(folder, exist_ok=True)
    file.save(os.path.join(folder, stamped_name))

    doc = PartyDocument(
        party_type=party_type,
        party_id=party_id,
        document_title=title or None,
        file_name=safe_name,
        # Stored/served path hamesha forward-slash se — send_from_directory OS-independent
        # (/) rules se path check karta hai, Windows backslash isse 404 deta (seekha PO upload se)
        file_path=folder_name + "/" + str(party_id) + "/" + stamped_name,
        file_size=size,
        is_deleted=False,
    )
    db.session.add(doc)
    db.session.commit()

    return jsonify(success=True)


@party_documents_bp.route("/party_documents/<int:doc_id>/delete", methods=["POST"])
def party_documents_delete(doc_id):
    doc = PartyDocument.query.get_or_404(doc_id)
    doc.is_deleted = True
    db.session.commit()
    return jsonify(success=True)


@party_documents_bp.route("/party_documents/<int:doc_id>/file")
def party_documents_file(doc_id):
    doc = PartyDocument.query.get_or_404(doc_id)
    if doc.is_deleted:
        abort(404)
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], doc.file_path)
