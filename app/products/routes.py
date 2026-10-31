import os
from werkzeug.utils import secure_filename
from flask import render_template, Blueprint, redirect, url_for, request, flash
from sqlalchemy import or_
from app.models import Product, ProductCategories, Unit, TaxRate, RawMaterial, VariantRecipeItem, WorkStage, ProductRoutingStage, ProductPackingItem
from app.extensions import db
from datetime import datetime

products_bp = Blueprint("products", __name__, template_folder='templates')

def generate_next_product_code():
    last = Product.query.order_by(Product.id.desc()).first()
    if not last:
        return "FG-0001"
    return f"FG-{last.id + 1:04d}"

def read_min_max():
    """Form se Min / Max stock (KG, whole number, khaali ho sakta hai). Return (min, max, error)."""
    values = []
    for field in ("min_stock", "max_stock"):
        raw = (request.form.get(field) or "").strip()
        if not raw:
            values.append(None)
            continue
        try:
            number = int(raw)
        except ValueError:
            return None, None, "Min and max stock must be whole numbers."
        if number < 0:
            return None, None, "Min and max stock cannot be negative."
        values.append(number)
    if values[0] is not None and values[1] is not None and values[0] > values[1]:
        return None, None, "Min stock cannot be more than max stock."
    return values[0], values[1], None


@products_bp.route("/products")
def products_list():

    products = Product.query.filter(Product.is_deleted == False).order_by(Product.code).all()
    total_count = len(products)

    units = Unit.query.filter(Unit.is_deleted == False, Unit.is_active == True).all()
    categories = ProductCategories.query.filter(ProductCategories.is_deleted == False,              ProductCategories.is_active == True).all()
    tax_rates = TaxRate.query.filter(TaxRate.is_active == True, TaxRate.is_deleted == False).order_by(TaxRate.code).all()
    # Recipe dropdown: sirf jin RM pe Base metal ya Core flux tick hai
    recipe_materials = RawMaterial.query.filter(
        RawMaterial.is_deleted == False,
        RawMaterial.is_active == True,
        or_(RawMaterial.is_base_metal == True, RawMaterial.is_core_flux == True),
    ).order_by(RawMaterial.code).all()
    # Packing Material dropdown: sirf jin RM pe "Packing" role hai
    packing_materials = RawMaterial.query.filter(
        RawMaterial.is_deleted == False, RawMaterial.is_active == True, RawMaterial.is_packing == True,
    ).order_by(RawMaterial.code).all()

    next_code = generate_next_product_code()

    return render_template(
        "products.html",
        active_nav='products',
        next_code=next_code,
        products=products,
        total_count=total_count,
        result_count=total_count,
        categories=categories,
        units=units,
        tax_rates=tax_rates,
        recipe_materials=recipe_materials,
        packing_materials=packing_materials,
        routing_stages=WorkStage.query.filter(WorkStage.is_deleted == False, WorkStage.is_active == True).order_by(WorkStage.sort_order, WorkStage.id).all(),
    )


@products_bp.route("/products/routing/<int:p_id>", methods=["POST"])
def products_routing(p_id):
    # Product ke default production stages save karo. Ye configuration hai (business document nahi), isliye purani list badal di jaati hai.
    product = Product.query.filter_by(id=p_id, is_deleted=False).first_or_404()
    wanted = []
    for stage_id in request.form.getlist("stage_id", type=int):
        stage = db.session.get(WorkStage, stage_id)
        if stage is None or stage.is_deleted or not stage.is_active:
            flash("One of the chosen stages is not available.", "error")
            return redirect(url_for("products.products_list"))
        if stage_id not in wanted:
            wanted.append(stage_id)
    for row in list(product.routing_stages):
        db.session.delete(row)
    db.session.flush()
    for stage_id in wanted:
        db.session.add(ProductRoutingStage(product_id=product.id, work_stage_id=stage_id))
    db.session.commit()
    flash(f"Production stages saved for {product.name}: {len(wanted)} stage{'' if len(wanted) == 1 else 's'}.", "success")
    return redirect(url_for("products.products_list"))

@products_bp.route("/products/add", methods=['POST'])
def products_add():
    code = generate_next_product_code()
    category_id = int(request.form.get('category_id')) if (request.form.get('category_id') or "").strip() else None
    description = (request.form.get('description') or "").strip()
    base_unit_id = int(request.form.get('base_unit_id')) if (request.form.get('base_unit_id') or "").strip() else None
    hsn_code = (request.form.get('hsn_code') or "").strip()
    tax_rate_id = int(request.form.get('tax_rate_id')) if (request.form.get('tax_rate_id') or "").strip() else None
    min_stock, max_stock, mm_error = read_min_max()
    if mm_error:
        flash(mm_error, "error")
        return redirect(url_for('products.products_list'))
    cat = ProductCategories.query.get(category_id) if category_id else None
    attr_keys = request.form.getlist('attr_key_0[]')
    attr_values = request.form.getlist('attr_value_0[]')

    attributes = {}
    parts = [cat.name.strip()] if cat else []
    for k,v in zip(attr_keys, attr_values):
        key = (k or "").strip()
        value = (v or "").strip()
        if not key:
            continue
        attributes[key]=value
        if value:
            parts.append(value)

    name = " ".join(parts)[:100]

    dup_name = Product.query.filter(Product.name == name, Product.is_deleted == False).first()
    if name and dup_name:
        flash("A product with this name already exists.", "error")
        return redirect(url_for('products.products_list'))


    if not code or not name or category_id is None or base_unit_id is None or tax_rate_id is None:
        return redirect(url_for('products.products_list'))

    existing = Product.query.filter(Product.code == code).first()
    if existing:
        if existing.is_deleted:
            existing.is_deleted = False
            existing.code = code
            existing.name = name
            existing.description = description
            existing.category_id = category_id
            existing.attributes = attributes
            existing.base_unit_id = base_unit_id
            existing.tax_rate_id = tax_rate_id
            existing.hsn_code = hsn_code
            existing.min_stock = min_stock
            existing.max_stock = max_stock
            existing.is_active = True
            db.session.commit()
            flash("A Product restored with this code.", "success")    
            return redirect(url_for('products.products_list'))

        flash("A Product with this code already exists.", "error")    
        return redirect(url_for('products.products_list'))

    product = Product(
        code=code,
        name=name,
        description=description,
        category_id=category_id,
        attributes=attributes,
        base_unit_id=base_unit_id,
        tax_rate_id=tax_rate_id,
        hsn_code=hsn_code,
        min_stock=min_stock,
        max_stock=max_stock,
        is_active=True,
        is_deleted=False,
    )
    db.session.add(product)   
    db.session.flush()

    recipe_rms = (request.form.getlist('recipe_rm_id[]'))
    recipe_ratios = (request.form.getlist('recipe_ratio[]'))

    recipe_stages = request.form.getlist('recipe_stage[]')          # har recipe line ka "kis stage me" (khaali = koi nahi)
    for idx, (rm_id_str, ratio_str) in enumerate(zip(recipe_rms, recipe_ratios)):
        rm_id_str = (rm_id_str or "").strip()
        ratio_str = (ratio_str or "").strip()
        stage_id = None
        if idx < len(recipe_stages) and (recipe_stages[idx] or "").strip().isdigit():
            ws = WorkStage.query.get(int(recipe_stages[idx]))
            stage_id = ws.id if ws and not ws.is_deleted else None
        
        if rm_id_str and ratio_str:
            try:
                rm_id = int(rm_id_str)
                ratio = float(ratio_str)

                if ratio > 0:
                    rm = RawMaterial.query.get(rm_id)
                    # Galat id pe rm None hota hai — rm.id crash karta, isliye skip
                    if not rm:
                        continue
                    is_flux = bool(rm.is_core_flux)

                    db.session.add(VariantRecipeItem(
                       variant_id=None,
                       product_id=product.id,
                       raw_material_id=rm.id,
                       ratio_percent=ratio,
                       is_flux=is_flux, 
                       work_stage_id=stage_id,
                    ))
            except (ValueError, TypeError):
                continue

    # Packing Material (spool / sleeve / box): "har X KG par 1 pack". Edit par purani lines hata ke nayi (recipe jaisa hi tareeka)
    
    pk_rms = request.form.getlist('packing_rm_id[]')
    pk_kgs = request.form.getlist('packing_kg[]')
    seen_pk = set()
    for rm_id_str, kg_str in zip(pk_rms, pk_kgs):
        try:
            rm = RawMaterial.query.get(int((rm_id_str or '').strip()))
            kg = float((kg_str or '').strip())
        except (ValueError, TypeError):
            continue
        if not rm or rm.is_deleted or not rm.is_packing or kg <= 0 or rm.id in seen_pk:
            continue
        seen_pk.add(rm.id)
        db.session.add(ProductPackingItem(product_id=product.id, raw_material_id=rm.id, kg_per_pack=kg))

    if cat:
        fields = list(cat.attribute_fields or [])
        known = {f.lower() for f in fields}
        for key in attributes:
            if key.lower() not in known:
                fields.append(key)
                known.add(key.lower())
        cat.attribute_fields = fields
                    
    db.session.commit()
    flash(f"Product {product.code} and Recipe saved successfully.", "success")
    return redirect(url_for("products.products_list"))                    


@products_bp.route('/products/toggle/<int:p_id>', methods=['POST'])
def products_toggle(p_id):
    p = Product.query.get_or_404(p_id)

    p.is_active = not p.is_active
    db.session.commit()
    return redirect(url_for('products.products_list'))     

@products_bp.route('/products/edit/<int:p_id>', methods=['POST'])
def products_edit(p_id):
    p = Product.query.get_or_404(p_id)

    category_id = int(request.form.get('category_id')) if (request.form.get('category_id') or "").strip() else None
    description = (request.form.get('description') or "").strip()
    base_unit_id = int(request.form.get('base_unit_id')) if (request.form.get('base_unit_id') or "").strip() else None
    hsn_code = (request.form.get('hsn_code') or "").strip()
    tax_rate_id = int(request.form.get('tax_rate_id')) if (request.form.get('tax_rate_id') or "").strip() else None
    min_stock, max_stock, mm_error = read_min_max()
    if mm_error:
        flash(mm_error, "error")
        return redirect(url_for('products.products_list'))
    cat = ProductCategories.query.get(category_id) if category_id else None
    attr_keys = request.form.getlist('attr_key_0[]')
    attr_values = request.form.getlist('attr_value_0[]')

    attributes = {}
    parts = [cat.name.strip()] if cat else []
    for k,v in zip(attr_keys, attr_values):
        key = (k or "").strip()
        value = (v or "").strip()
        if not key:
            continue
        attributes[key]=value
        if value:
            parts.append(value)

    name = " ".join(parts)[:100]

    if category_id is None or base_unit_id is None or tax_rate_id is None:
        return redirect(url_for('products.products_list'))

    dup_name = Product.query.filter(Product.name == name, Product.is_deleted == False, Product.id != p_id,).first()
    if name and dup_name:
        flash("A product with this name already exists.", "error")
        return redirect(url_for('products.products_list'))

    p.name = name
    p.description = description
    p.category_id = category_id
    p.attributes = attributes
    p.base_unit_id = base_unit_id
    p.tax_rate_id = tax_rate_id
    p.hsn_code = hsn_code
    p.min_stock = min_stock
    p.max_stock = max_stock
    p.is_deleted = False

    VariantRecipeItem.query.filter_by(product_id=p.id).delete()

    recipe_rms = (request.form.getlist('recipe_rm_id[]'))
    recipe_ratios = (request.form.getlist('recipe_ratio[]'))

    recipe_stages = request.form.getlist('recipe_stage[]')          # har recipe line ka "kis stage me" (khaali = koi nahi)
    for idx, (rm_id_str, ratio_str) in enumerate(zip(recipe_rms, recipe_ratios)):
        rm_id_str = (rm_id_str or "").strip()
        ratio_str = (ratio_str or "").strip()
        stage_id = None
        if idx < len(recipe_stages) and (recipe_stages[idx] or "").strip().isdigit():
            ws = WorkStage.query.get(int(recipe_stages[idx]))
            stage_id = ws.id if ws and not ws.is_deleted else None
        
        if rm_id_str and ratio_str:
            try:
                rm_id = int(rm_id_str)
                ratio = float(ratio_str)

                if ratio > 0:
                    rm = RawMaterial.query.get(rm_id)
                    # Galat id pe rm None hota hai — rm.id crash karta, isliye skip
                    if not rm:
                        continue
                    is_flux = bool(rm.is_core_flux)

                    db.session.add(VariantRecipeItem(
                       variant_id=None,
                       product_id=p.id,
                       raw_material_id=rm.id,
                       ratio_percent=ratio,
                       is_flux=is_flux, 
                       work_stage_id=stage_id,
                    ))
            except (ValueError, TypeError):
                continue


    # Packing Material (spool / sleeve / box): "har X KG par 1 pack". Edit par purani lines hata ke nayi (recipe jaisa hi tareeka)
    ProductPackingItem.query.filter_by(product_id=p.id).delete()
    pk_rms = request.form.getlist('packing_rm_id[]')
    pk_kgs = request.form.getlist('packing_kg[]')
    seen_pk = set()
    for rm_id_str, kg_str in zip(pk_rms, pk_kgs):
        try:
            rm = RawMaterial.query.get(int((rm_id_str or '').strip()))
            kg = float((kg_str or '').strip())
        except (ValueError, TypeError):
            continue
        if not rm or rm.is_deleted or not rm.is_packing or kg <= 0 or rm.id in seen_pk:
            continue
        seen_pk.add(rm.id)
        db.session.add(ProductPackingItem(product_id=p.id, raw_material_id=rm.id, kg_per_pack=kg))

    if cat:
        fields = list(cat.attribute_fields or [])
        known = {f.lower() for f in fields}
        for key in attributes:
            if key.lower() not in known:
                fields.append(key)
                known.add(key.lower())
        cat.attribute_fields = fields
        
    db.session.commit()
    flash("Product updated.", "success")   
    return redirect(url_for('products.products_list'))

@products_bp.route('/products/delete/<int:p_id>', methods=['POST'])
def products_delete(p_id):
    p = Product.query.get_or_404(p_id)

    p.is_deleted = True
    db.session.commit()

    flash("Product removed from the list (kept in database).", "success")
    return redirect(url_for('products.products_list'))

# Variant add/edit/delete ab use nahi hote. Ek product = ek spec. Attributes aur recipe product pe hain.
# @products_bp.route('/products/<int:p_id>/variants/add', methods=['POST'])
# def products_variants_add(p_id):
#     p = Product.query.get_or_404(p_id)

#     variant_name = (request.form.get('name') or "").strip()
#     taken = ProductVariant.query.filter_by(product_id=p_id).count()
#     variant_sku = f"{p.code}-{taken + 1:02d}"
#     attr_keys = request.form.getlist('attr_key[]')
#     attr_values = request.form.getlist('attr_value[]')

#     if not variant_name or not variant_sku:
#         return redirect(url_for('products.products_list'))

#     attributes = {}
#     for k, v in zip(attr_keys, attr_values):
#         k = k.strip()
#         if k:
#             attributes[k] = v.strip()

#     existing = ProductVariant.query.filter_by(sku=variant_sku).first()
#     if existing:
#         if existing.is_deleted:
#             existing.is_deleted = False
#             existing.product_id = p_id
#             existing.sku = variant_sku
#             existing.name = variant_name
#             existing.attributes = attributes
#             existing.is_active = True
#             VariantRecipeItem.query.filter_by(variant_id=existing.id).delete()
#             recipe_rms = request.form.getlist('recipe_rm_id[]')
#             recipe_ratios = request.form.getlist('recipe_ratio[]')
#             for rm_id_str, ratio_str in zip(recipe_rms, recipe_ratios):
#                 rm_id_str = (rm_id_str or "").strip()
#                 ratio_str = (ratio_str or "").strip()
#                 if not rm_id_str or not ratio_str:
#                     continue
#                 try:
#                     rm_id = int(rm_id_str)
#                     ratio = float(ratio_str)
#                 except (ValueError, TypeError):
#                     continue
#                 if ratio <= 0:
#                     continue
#                 rm = RawMaterial.query.get(rm_id)
#                 if not rm:
#                     continue
#                 db.session.add(VariantRecipeItem(
#                     variant_id=existing.id,
#                     raw_material_id=rm.id,
#                     ratio_percent=ratio,
#                     is_flux=rm.is_core_flux,
#                 ))
#             db.session.commit()
#             flash("A Product Variant restored with this SKU.", "success")
#             return redirect(url_for('products.products_list'))
#         flash("A Product Variant with this SKU already exists.", "error")
#         return redirect(url_for('products.products_list'))        

#     pv = ProductVariant(
#         product_id = p_id,
#         sku = variant_sku,
#         name = variant_name,
#         attributes = attributes,
#         is_active = True,
#         is_deleted = False,
#     )
#     db.session.add(pv)
#     db.session.flush()

#     recipe_rms = (request.form.getlist('recipe_rm_id[]'))
#     recipe_ratios = (request.form.getlist('recipe_ratio[]'))

#     for rm_id_str, ratio_str in zip(recipe_rms, recipe_ratios):
#         rm_id_str = (rm_id_str or "").strip()
#         ratio_str = (ratio_str or "").strip()

#         if rm_id_str and ratio_str:
#             try: 
#                 rm_id = int(rm_id_str)
#                 ratio = float(ratio_str)
#             except (ValueError, TypeError):
#                 continue    
#             if ratio > 0:
#                 rm = RawMaterial.query.get(rm_id)
#                 if not rm:
#                     continue
#                 is_core_flux = rm.is_core_flux

#                 db.session.add(VariantRecipeItem( variant_id=pv.id,
#                     raw_material_id=rm.id,
#                     ratio_percent=ratio,
#                     is_flux=is_core_flux,
#                     ))
#     db.session.commit()
#     flash("Product Variant added.", "success")
#     return redirect(url_for('products.products_list'))

# @products_bp.route('/products/variants/edit/<int:v_id>', methods=['POST'])
# def products_variants_edit(v_id):
#     pv = ProductVariant.query.get_or_404(v_id)

#     variant_name = (request.form.get('name') or "").strip()
#     attr_keys = request.form.getlist('attr_key[]')
#     attr_values = request.form.getlist('attr_value[]')

#     if not variant_name:
#         return redirect(url_for('products.products_list'))

#     attributes = {}    
#     for k, v in zip(attr_keys, attr_values):
#         k = k.strip()
#         if k:
#             attributes[k] = v.strip()        


#     pv.name = variant_name
#     pv.attributes = attributes
#     pv.is_deleted = False

#     VariantRecipeItem.query.filter_by(variant_id=pv.id).delete()

#     recipe_rms = (request.form.getlist('recipe_rm_id[]'))
#     recipe_ratios = (request.form.getlist('recipe_ratio[]'))

#     for rm_id_str, ratio_str in zip(recipe_rms, recipe_ratios):
#         rm_id_str = (rm_id_str or "").strip()
#         ratio_str = (ratio_str or "").strip()

#         if rm_id_str and ratio_str:
#             try: 
#                 rm_id = int(rm_id_str)
#                 ratio = float(ratio_str)
#             except (ValueError, TypeError):
#                 continue    
#             if ratio > 0:
#                 rm = RawMaterial.query.get(rm_id)
#                 if not rm:
#                     continue
#                 is_core_flux = rm.is_core_flux

#                 db.session.add(VariantRecipeItem( variant_id=pv.id,
#                     raw_material_id=rm.id,
#                     ratio_percent=ratio,
#                     is_flux=is_core_flux,
#                     ))    

#     db.session.commit()
#     flash("Product Variant updated.", "success")   
#     return redirect(url_for('products.products_list'))

# @products_bp.route('/products/variants/delete/<int:v_id>', methods=['POST'])
# def products_variants_delete(v_id):
#     pv = ProductVariant.query.get_or_404(v_id)

#     pv.is_deleted = True
#     db.session.commit()
#     flash("Product Variant removed (kept in database).", "success")
#     return redirect(url_for('products.products_list'))