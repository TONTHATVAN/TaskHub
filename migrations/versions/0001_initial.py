"""Initial TaskHub schema."""

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE users (
        	id UUID NOT NULL, 
        	email VARCHAR(320) NOT NULL, 
        	full_name VARCHAR(200) NOT NULL, 
        	hashed_password VARCHAR(255) NOT NULL, 
        	role VARCHAR(6) NOT NULL, 
        	is_active BOOLEAN NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	PRIMARY KEY (id), 
        	CONSTRAINT userrole CHECK (role IN ('ADMIN', 'MEMBER'))
        )
        """
    )
    op.execute(
        """
        CREATE TABLE workspaces (
        	id UUID NOT NULL, 
        	name VARCHAR(200) NOT NULL, 
        	owner_id UUID NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	PRIMARY KEY (id), 
        	FOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE RESTRICT
        )
        """
    )
    op.execute(
        """
        CREATE TABLE projects (
        	id UUID NOT NULL, 
        	workspace_id UUID NOT NULL, 
        	name VARCHAR(200) NOT NULL, 
        	description TEXT, 
        	status VARCHAR(8) NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	PRIMARY KEY (id), 
        	FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE, 
        	CONSTRAINT projectstatus CHECK (status IN ('ACTIVE', 'ARCHIVED'))
        )
        """
    )
    op.execute(
        """
        CREATE TABLE workspace_members (
        	workspace_id UUID NOT NULL, 
        	user_id UUID NOT NULL, 
        	role VARCHAR(6) NOT NULL, 
        	PRIMARY KEY (workspace_id, user_id), 
        	FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE, 
        	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
        	CONSTRAINT workspacerole CHECK (role IN ('OWNER', 'EDITOR', 'VIEWER'))
        )
        """
    )
    op.execute(
        """
        CREATE TABLE labels (
        	id UUID NOT NULL, 
        	project_id UUID NOT NULL, 
        	name VARCHAR(100) NOT NULL, 
        	color VARCHAR(7) NOT NULL, 
        	PRIMARY KEY (id), 
        	UNIQUE (project_id, name), 
        	UNIQUE (id, project_id), 
        	FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE
        )
        """
    )
    op.execute(
        """
        CREATE TABLE tasks (
        	id UUID NOT NULL, 
        	project_id UUID NOT NULL, 
        	assignee_id UUID, 
        	title VARCHAR(200) NOT NULL, 
        	description TEXT, 
        	status VARCHAR(11) NOT NULL, 
        	priority VARCHAR(6) NOT NULL, 
        	due_date TIMESTAMP WITH TIME ZONE, 
        	created_by UUID, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	PRIMARY KEY (id), 
        	FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
        	FOREIGN KEY(assignee_id) REFERENCES users (id) ON DELETE SET NULL, 
        	CONSTRAINT taskstatus CHECK (status IN ('TODO', 'IN_PROGRESS', 'IN_REVIEW', 'DONE')), 
        	CONSTRAINT taskpriority CHECK (priority IN ('LOW', 'MEDIUM', 'HIGH', 'URGENT')), 
        	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE comments (
        	id UUID NOT NULL, 
        	task_id UUID NOT NULL, 
        	author_id UUID NOT NULL, 
        	content TEXT NOT NULL, 
        	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
        	PRIMARY KEY (id), 
        	FOREIGN KEY(task_id) REFERENCES tasks (id) ON DELETE CASCADE, 
        	FOREIGN KEY(author_id) REFERENCES users (id) ON DELETE RESTRICT
        )
        """
    )
    op.execute(
        """
        CREATE TABLE task_labels (
        	task_id UUID NOT NULL, 
        	label_id UUID NOT NULL, 
        	PRIMARY KEY (task_id, label_id), 
        	FOREIGN KEY(task_id) REFERENCES tasks (id) ON DELETE CASCADE, 
        	FOREIGN KEY(label_id) REFERENCES labels (id) ON DELETE CASCADE
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX ix_users_email ON users (email)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_workspaces_owner_id ON workspaces (owner_id)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_projects_workspace_id ON projects (workspace_id)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_labels_project_id ON labels (project_id)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_tasks_assignee_id ON tasks (assignee_id)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_tasks_priority ON tasks (priority)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_tasks_project_id ON tasks (project_id)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_tasks_status ON tasks (status)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_comments_author_id ON comments (author_id)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_comments_task_id ON comments (task_id)
        """
    )


def downgrade() -> None:
    op.drop_table('task_labels')
    op.drop_table('comments')
    op.drop_table('tasks')
    op.drop_table('labels')
    op.drop_table('workspace_members')
    op.drop_table('projects')
    op.drop_table('workspaces')
    op.drop_table('users')
