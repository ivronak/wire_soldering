from flask import render_template, Blueprint, redirect, url_for, request, flash
from sqlalchemy import or_
from app.models import Product, ProductCategories, Unit, TaxRate, ProductVariant, RawMaterial, VariantRecipeItem
from app.extensions import db

products_bp = Blueprint("products", __name__, template_folder="templates")

def generate_next_product_code():
    last = Product.query.order_by(Product.id.desc()).first()
    if not last:
        return "FG-0001"
    return f"FG-{last.id + 1:04d}"

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
    )

@products_bp.route("/products/add", methods=['POST'])
def products_add():
    code = generate_next_product_code()
    name = (request.form.get('name') or "").strip()
    category_id = int(request.form.get('category_id')) if (request.form.get('category_id') or "").strip() else None
    description = (request.form.get('description') or "").strip()
    base_unit_id = int(request.form.get('base_unit_id')) if (request.form.get('base_unit_id') or "").strip() else None
    hsn_code = (request.form.get('hsn_code') or "").strip()
    tax_rate_id = int(request.form.get('tax_rate_id')) if (request.form.get('tax_rate_id') or "").strip() else None

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
            existing.base_unit_id = base_unit_id
            existing.tax_rate_id = tax_rate_id
            existing.hsn_code = hsn_code
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
        base_unit_id=base_unit_id,
        tax_rate_id=tax_rate_id,
        hsn_code=hsn_code,
        is_active=True,
        is_deleted=False,
    )
    db.session.add(product)   
    db.session.flush()

    attr_keys = request.form.getlist(f'attr_key_0[]')
    attr_values = request.form.getlist(f'attr_value_0[]')

    attributes = {}
    for k,v in zip(attr_keys, attr_values):
        k = k.strip()
        if k:
            attributes[k]=v.strip()

    # Variant name column 100 chars hai — lamba product name "-Standard" ke saath cut ho jaata
    variant_name = f"{name}-Standard"
    if len(variant_name) > 100:
        variant_name = variant_name[:100]

    default_variant = ProductVariant(
        product_id=product.id,
        name=variant_name,
        sku = f"{code}-STD",
        attributes=attributes,
        is_active = True,
       is_deleted = False,
    )

    db.session.add(default_variant)
    db.session.flush()

    recipe_rms = (request.form.getlist('recipe_rm_id[]'))
    recipe_ratios = (request.form.getlist('recipe_ratio[]'))

    for rm_id_str, ratio_str in zip(recipe_rms, recipe_ratios):
        rm_id_str = (rm_id_str or "").strip()
        ratio_str = (ratio_str or "").strip()
        
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
                       variant_id=default_variant.id,
                       raw_material_id=rm.id,
                       ratio_percent=ratio,
                       is_flux=is_flux, 
                    ))
            except (ValueError, TypeError):
                continue
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

    name = (request.form.get('name') or "").strip()
    category_id = int(request.form.get('category_id')) if (request.form.get('category_id') or "").strip() else None
    description = (request.form.get('description') or "").strip()
    base_unit_id = int(request.form.get('base_unit_id')) if (request.form.get('base_unit_id') or "").strip() else None
    hsn_code = (request.form.get('hsn_code') or "").strip()
    tax_rate_id = int(request.form.get('tax_rate_id')) if (request.form.get('tax_rate_id') or "").strip() else None

    if not name or category_id is None or base_unit_id is None or tax_rate_id is None:
        return redirect(url_for('products.products_list'))

    p.name = name
    p.description = description
    p.category_id = category_id
    p.base_unit_id = base_unit_id
    p.tax_rate_id = tax_rate_id
    p.hsn_code = hsn_code
    p.is_deleted = False

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

@products_bp.route('/products/<int:p_id>/variants/add', methods=['POST'])
def products_variants_add(p_id):
    p = Product.query.get_or_404(p_id)

    variant_name = (request.form.get('name') or "").strip()
    taken = ProductVariant.query.filter_by(product_id=p_id).count()
    variant_sku = f"{p.code}-{taken + 1:02d}"
    attr_keys = request.form.getlist('attr_key[]')
    attr_values = request.form.getlist('attr_value[]')

    if not variant_name or not variant_sku:
        return redirect(url_for('products.products_list'))

    attributes = {}
    for k, v in zip(attr_keys, attr_values):
        k = k.strip()
        if k:
            attributes[k] = v.strip()

    existing = ProductVariant.query.filter_by(sku=variant_sku).first()
    if existing:
        if existing.is_deleted:
            existing.is_deleted = False
            existing.product_id = p_id
            existing.sku = variant_sku
            existing.name = variant_name
            existing.attributes = attributes
            existing.is_active = True
            VariantRecipeItem.query.filter_by(variant_id=existing.id).delete()
            recipe_rms = request.form.getlist('recipe_rm_id[]')
            recipe_ratios = request.form.getlist('recipe_ratio[]')
            for rm_id_str, ratio_str in zip(recipe_rms, recipe_ratios):
                rm_id_str = (rm_id_str or "").strip()
                ratio_str = (ratio_str or "").strip()
                if not rm_id_str or not ratio_str:
                    continue
                try:
                    rm_id = int(rm_id_str)
                    ratio = float(ratio_str)
                except (ValueError, TypeError):
                    continue
                if ratio <= 0:
                    continue
                rm = RawMaterial.query.get(rm_id)
                if not rm:
                    continue
                db.session.add(VariantRecipeItem(
                    variant_id=existing.id,
                    raw_material_id=rm.id,
                    ratio_percent=ratio,
                    is_flux=rm.is_core_flux,
                ))
            db.session.commit()
            flash("A Product Variant restored with this SKU.", "success")
            return redirect(url_for('products.products_list'))
        flash("A Product Variant with this SKU already exists.", "error")
        return redirect(url_for('products.products_list'))        

    pv = ProductVariant(
        product_id = p_id,
        sku = variant_sku,
        name = variant_name,
        attributes = attributes,
        is_active = True,
        is_deleted = False,
    )
    db.session.add(pv)
    db.session.flush()

    recipe_rms = (request.form.getlist('recipe_rm_id[]'))
    recipe_ratios = (request.form.getlist('recipe_ratio[]'))

    for rm_id_str, ratio_str in zip(recipe_rms, recipe_ratios):
        rm_id_str = (rm_id_str or "").strip()
        ratio_str = (ratio_str or "").strip()

        if rm_id_str and ratio_str:
            try: 
                rm_id = int(rm_id_str)
                ratio = float(ratio_str)
            except (ValueError, TypeError):
                continue    
            if ratio > 0:
                rm = RawMaterial.query.get(rm_id)
                if not rm:
                    continue
                is_core_flux = rm.is_core_flux

                db.session.add(VariantRecipeItem( variant_id=pv.id,
                    raw_material_id=rm.id,
                    ratio_percent=ratio,
                    is_flux=is_core_flux,
                    ))
    db.session.commit()
    flash("Product Variant added.", "success")
    return redirect(url_for('products.products_list'))

@products_bp.route('/products/variants/edit/<int:v_id>', methods=['POST'])
def products_variants_edit(v_id):
    pv = ProductVariant.query.get_or_404(v_id)

    variant_name = (request.form.get('name') or "").strip()
    attr_keys = request.form.getlist('attr_key[]')
    attr_values = request.form.getlist('attr_value[]')

    if not variant_name:
        return redirect(url_for('products.products_list'))

    attributes = {}    
    for k, v in zip(attr_keys, attr_values):
        k = k.strip()
        if k:
            attributes[k] = v.strip()        
           

    pv.name = variant_name
    pv.attributes = attributes
    pv.is_deleted = False

    VariantRecipeItem.query.filter_by(variant_id=pv.id).delete()

    recipe_rms = (request.form.getlist('recipe_rm_id[]'))
    recipe_ratios = (request.form.getlist('recipe_ratio[]'))

    for rm_id_str, ratio_str in zip(recipe_rms, recipe_ratios):
        rm_id_str = (rm_id_str or "").strip()
        ratio_str = (ratio_str or "").strip()

        if rm_id_str and ratio_str:
            try: 
                rm_id = int(rm_id_str)
                ratio = float(ratio_str)
            except (ValueError, TypeError):
                continue    
            if ratio > 0:
                rm = RawMaterial.query.get(rm_id)
                if not rm:
                    continue
                is_core_flux = rm.is_core_flux

                db.session.add(VariantRecipeItem( variant_id=pv.id,
                    raw_material_id=rm.id,
                    ratio_percent=ratio,
                    is_flux=is_core_flux,
                    ))    

    db.session.commit()
    flash("Product Variant updated.", "success")   
    return redirect(url_for('products.products_list'))

@products_bp.route('/products/variants/delete/<int:v_id>', methods=['POST'])
def products_variants_delete(v_id):
    pv = ProductVariant.query.get_or_404(v_id)

    pv.is_deleted = True
    db.session.commit()
    flash("Product Variant removed (kept in database).", "success")
    return redirect(url_for('products.products_list'))