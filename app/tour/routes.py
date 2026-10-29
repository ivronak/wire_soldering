# Demo tour ke helper endpoints (sirf tour use karta hai):
#   GET  /tour/info                      -> tour ke "Demo value bharo" button ke liye: recipe wala pehla product, uske materials, store warehouse, pehla vendor (PO ke liye)
#   POST /tour/finish_stages/<order_id>  -> demo shortcut: In production order ke baaki routing stages (8 me se 6 jaise) ek click me poore
# Shortcut wahi asli rules follow karta hai (stage ek ke baad ek, qty in -> out, machines used); sirf typing bachata hai.
from datetime import timedelta

import os

from flask import Blueprint, current_app, jsonify, render_template, request

from app.extensions import db
from app.models import Product, ProductionOrder, StageLabQC, Vendor, Warehouse, WorkStage
from app.production_orders.scheduler import now_ist
from app.routing.routes import order_batch_kg

tour_bp = Blueprint("tour", __name__, template_folder="templates")


@tour_bp.route("/tour/info")
def tour_info():
    # Demo ke liye wo product jiski recipe + routing bani ho (sabse pehla)
    product = None
    for candidate in Product.query.filter_by(is_deleted=False, is_active=True).order_by(Product.id).all():
        if candidate.recipe_items and candidate.routing_stages:
            product = candidate
            break
    store = Warehouse.query.filter_by(warehouse_type="RM", is_active=True, is_deleted=False).order_by(Warehouse.id).first()
    if product is None:
        return jsonify({"ok": False, "message": "No product with a recipe and routing stages was found."})
    # Procurement demo (PO) ke liye pehla active vendor
    vendor = Vendor.query.filter_by(is_deleted=False, is_active=True).order_by(Vendor.id).first()
    recipe = []
    for item in product.recipe_items:
        rm = item.raw_material
        recipe.append({"rm_id": item.raw_material_id, "code": rm.code if rm else "", "name": rm.name if rm else "",
                       "unit": rm.base_unit.code if rm and rm.base_unit else "", "ratio": item.ratio_percent})
    lab_qc = WorkStage.query.filter_by(is_deleted=False, is_active=True, requires_lab_qc=True).first() is not None
    return jsonify({"ok": True, "product": {"id": product.id, "name": product.name, "category_id": product.category_id, "recipe": recipe},
                    "store_warehouse_id": store.id if store else None,
                    "vendor_id": vendor.id if vendor else None, "lab_qc": lab_qc})


@tour_bp.route("/tour/finish_stages/<int:order_id>", methods=["POST"])
def tour_finish_stages(order_id):
    order = ProductionOrder.query.filter_by(id=order_id, is_deleted=False).first_or_404()
    if order.status != "In production":
        return jsonify({"ok": False, "message": "The order is not in production."}), 400
    pending = [s for s in order.stages if s.status != "Done"]
    if not pending:
        return jsonify({"ok": True, "message": "All stages are already done."})
    done = [s for s in order.stages if s.status == "Done"]
    qty = done[-1].qty_out if done else order_batch_kg(order)
    now = now_ist().replace(second=0, microsecond=0)
    t0 = max([now - timedelta(hours=10)] + ([done[-1].completed_at + timedelta(minutes=5)] if done and done[-1].completed_at else []))
    window = (now - timedelta(minutes=5)) - t0
    slot = window / len(pending) if window.total_seconds() > 0 else timedelta(minutes=2)
    cursor = t0
    for stage in pending:
        if stage.status == "Pending":
            stage.status = "In progress"
            stage.started_at = cursor
            stage.operator = stage.operator or "Demo operator"
            stage.qty_in = qty
        stage.completed_at = max(cursor + slot * 0.9, stage.started_at + timedelta(minutes=1))
        for machine in stage.machines:
            machine.used = bool(machine.is_planned)
        stage.qty_out = qty
        stage.scrap_qty = 0
        stage.scrap_type_id = None
        stage.scrap_kind = "Saleable"
        stage.status = "Done"
        # Lab QC wala stage (Melting) ho to demo ek Pass test + nakli TC (chhoti PDF) bhi daal deta hai, taaki TC order se juda dikhe
        if stage.work_stage and stage.work_stage.requires_lab_qc and not any(q.result == "Pass" and q.tc_file for q in stage.lab_qcs):
            qc = StageLabQC(stage_id=stage.id, tested_at=stage.completed_at, tested_by="Demo lab", result="Pass", remarks="Demo tour")
            db.session.add(qc)
            db.session.flush()
            folder = os.path.join(current_app.config["UPLOAD_FOLDER"], "lab_qc", str(qc.id))
            os.makedirs(folder, exist_ok=True)
            with open(os.path.join(folder, "demo-tc.pdf"), "wb") as handle:
                handle.write(b"%PDF-1.1\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 120]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF")
            qc.tc_file = "lab_qc/" + str(qc.id) + "/demo-tc.pdf"
        cursor = stage.completed_at + timedelta(minutes=1)
    db.session.commit()
    return jsonify({"ok": True, "message": f"{len(pending)} stages completed (demo shortcut)."})


@tour_bp.route("/tour/order_id")
def tour_order_id():
    # Order no (PROD-2026-001) se id — demo shortcut button ko chahiye
    order = ProductionOrder.query.filter_by(prod_no=(request.args.get("no") or "").strip(), is_deleted=False).first()
    if order is None:
        return jsonify({"ok": False, "message": "Order not found."})
    return jsonify({"ok": True, "id": order.id})


@tour_bp.route("/demo")
def demo_player():
    # 1-click auto demo: ERP iframe me, step khud chalte hain, Gujarati awaaz parent page se (static/js/demo.js)
    return render_template("demo.html")
