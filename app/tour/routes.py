# Demo tour ke helper endpoints (sirf tour use karta hai):
#   GET  /tour/info                      -> tour ke "Demo value bharo" button ke liye: recipe wala pehla product, uske materials, store warehouse, pehla vendor (PO ke liye)
#   POST /tour/finish_stages/<order_id>  -> demo shortcut: In production order ke baaki routing stages (8 me se 6 jaise) ek click me poore
# Shortcut wahi asli rules follow karta hai (stage ek ke baad ek, qty in -> out, machines used); sirf typing bachata hai.
from datetime import timedelta

import os

from flask import Blueprint, current_app, jsonify, render_template, request

from app.extensions import db
from app.models import Product, ProductionLine, ProductionOrder, Rack, StageLabQC, Vendor, Warehouse, WorkStage
from app.production_orders.scheduler import now_ist
from app.routing.routes import order_batch_kg, side_stage_info

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
    # Naye features ke steps (Line, Rack, Scrap later, Wire Drawing 3) tabhi dikhte hain jab master me wo set ho
    scrap_later = WorkStage.query.filter_by(is_deleted=False, is_active=True, scrap_after_next=True).first() is not None
    wd_split = WorkStage.query.filter_by(is_deleted=False, is_active=True, name="Wire Drawing 3").first() is not None
    racks = bool(store) and Rack.query.filter_by(warehouse_id=store.id, is_active=True, is_deleted=False).first() is not None
    lines = ProductionLine.query.filter_by(is_active=True, is_deleted=False).first() is not None
    return jsonify({"ok": True, "product": {"id": product.id, "name": product.name, "category_id": product.category_id, "recipe": recipe},
                    "store_warehouse_id": store.id if store else None,
                    "vendor_id": vendor.id if vendor else None, "lab_qc": lab_qc,
                    "scrap_later": scrap_later, "wd_split": wd_split, "racks": racks, "lines": lines})


@tour_bp.route("/tour/shortage_order", methods=["POST"])
def tour_shortage_order():
    # Demo shortcut (Material plan ke liye): ek bada Draft order jiska maal stock me nahi, taaki plan me "kami" aur PO suggestion dikhe.
    # Asli order ki tarah /production_orders/add se banta hai (pehli line ki machines, jo line hai to).
    from app.models import Machines
    product = None
    for candidate in Product.query.filter_by(is_deleted=False, is_active=True).order_by(Product.id).all():
        if candidate.recipe_items and candidate.routing_stages:
            product = candidate
            break
    if product is None:
        return jsonify({"ok": False, "message": "No product with a recipe and routing stages was found."}), 400
    line = ProductionLine.query.filter_by(is_active=True, is_deleted=False).order_by(ProductionLine.id).first()
    data = [("order_date", now_ist().date().isoformat()), ("product_id", str(product.id)), ("planned_qty", "1500"), ("unit_weight", "1"),
            ("start_date", now_ist().date().isoformat()), ("remarks", "Demo: material plan")]
    if line is not None:
        data.append(("line_id", str(line.id)))
    for row in product.routing_stages:
        machines = Machines.query.filter_by(work_stage_id=row.work_stage_id, is_deleted=False, status="active")
        if line is not None:
            machines = machines.filter_by(line_id=line.id)
        data += [(f"machines_{row.work_stage_id}", str(m.id)) for m in machines.all()]
    from werkzeug.datastructures import MultiDict
    before = ProductionOrder.query.count()
    current_app.test_client().post("/production_orders/add", data=MultiDict(data))
    order = ProductionOrder.query.order_by(ProductionOrder.id.desc()).first()
    if ProductionOrder.query.count() == before or order is None:
        return jsonify({"ok": False, "message": "The demo order could not be created."}), 400
    return jsonify({"ok": True, "prod_no": order.prod_no})


@tour_bp.route("/tour/finish_stages/<int:order_id>", methods=["POST"])
def tour_finish_stages(order_id):
    order = ProductionOrder.query.filter_by(id=order_id, is_deleted=False).first_or_404()
    if order.status != "In production":
        return jsonify({"ok": False, "message": "The order is not in production."}), 400
    pending = [s for s in order.stages if s.status != "Done"]
    if not pending:
        return jsonify({"ok": True, "message": "All stages are already done."})
    done = [s for s in order.stages if s.status == "Done"]
    metal_done = [s for s in done if side_stage_info(order, s) is None]
    qty = metal_done[-1].qty_out if metal_done else order_batch_kg(order)
    now = now_ist().replace(second=0, microsecond=0)
    t0 = max([now - timedelta(hours=10)] + ([done[-1].completed_at + timedelta(minutes=5)] if done and done[-1].completed_at else []))
    window = (now - timedelta(minutes=5)) - t0
    slot = window / len(pending) if window.total_seconds() > 0 else timedelta(minutes=2)
    cursor = t0
    for stage in pending:
        side = side_stage_info(order, stage)                 # flux stage: apni qty, metal chain se alag
        if stage.status == "Pending":
            stage.status = "In progress"
            stage.started_at = cursor
            stage.operator = stage.operator or "Demo operator"
            stage.qty_in = side["qty"] if side else qty
        stage.completed_at = max(cursor + slot * 0.9, stage.started_at + timedelta(minutes=1))
        for machine in stage.machines:
            machine.used = bool(machine.is_planned)
        stage.qty_out = (stage.qty_in if side else qty)
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
