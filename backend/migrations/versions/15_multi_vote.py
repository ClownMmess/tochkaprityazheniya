"""Allow multiple selected events without losing existing votes."""
from alembic import op
import sqlalchemy as sa
revision = '15_multi_vote'
down_revision = '13_home_city'
branch_labels = None
depends_on = None


def upgrade():
    constraints = sa.inspect(op.get_bind()).get_unique_constraints('group_choice_votes')
    convention = {'uq': 'uq_%(table_name)s_%(column_0_name)s_%(column_1_name)s'}
    with op.batch_alter_table('group_choice_votes', naming_convention=convention) as batch:
        for item in constraints:
            if set(item['column_names']) == {'choice_id', 'user_id'}:
                batch.drop_constraint(item['name'] or 'uq_group_choice_votes_choice_id_user_id', type_='unique')
        batch.create_unique_constraint('uq_group_vote_option', ['choice_id', 'user_id', 'occurrence_id'])


def downgrade():
    multiple = op.get_bind().execute(sa.text('SELECT 1 FROM group_choice_votes GROUP BY choice_id,user_id HAVING COUNT(*)>1 LIMIT 1')).first()
    if multiple:
        raise RuntimeError('Cannot downgrade without discarding votes. Keep the current version.')
    with op.batch_alter_table('group_choice_votes') as batch:
        batch.drop_constraint('uq_group_vote_option', type_='unique')
        batch.create_unique_constraint('uq_group_choice_votes_choice_id_user_id', ['choice_id', 'user_id'])
