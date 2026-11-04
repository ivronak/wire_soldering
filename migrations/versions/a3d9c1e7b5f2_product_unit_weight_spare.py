"""product unit weight + spare percent on recipe and packing lines

Revision ID: a3d9c1e7b5f2
Revises: f2c8a5e1b7d3
Create Date: 2026-11-04 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a3d9c1e7b5f2'
down_revision = 'f2c8a5e1b7d3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.add_column(sa.Column('unit_weight', sa.Float(), nullable=True))
    with op.batch_alter_table('variant_recipe_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('spare_percent', sa.Float(), server_default='0', nullable=False))
    with op.batch_alter_table('product_packing_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('spare_percent', sa.Float(), server_default='0', nullable=False))
    # Purane PCS / ROLL wale products: 1 piece ka weight unki us packing line se jo product ki apni unit me hai (jaise 500G spool, 0.5 KG)
    op.execute(
        "UPDATE products SET unit_weight = ("
        "SELECT pi.kg_per_pack FROM product_packing_items pi JOIN raw_materials r ON r.id = pi.raw_material_id "
        "WHERE pi.product_id = products.id AND r.base_unit_id = products.base_unit_id ORDER BY pi.id LIMIT 1) "
        "WHERE base_unit_id IN (SELECT id FROM units WHERE upper(code) NOT IN ('KG', 'KGS'))"
    )


def downgrade():
    with op.batch_alter_table('product_packing_items', schema=None) as batch_op:
        batch_op.drop_column('spare_percent')
    with op.batch_alter_table('variant_recipe_items', schema=None) as batch_op:
        batch_op.drop_column('spare_percent')
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.drop_column('unit_weight')
