import streamlit as st
import uuid
import os

# --- Import Isolated AI Helper Module ---
try:
    from ai_helper import generate_task_blueprint
except ImportError:
    st.error("Could not find `ai_helper.py`. Please make sure it is saved in the same directory as this file.")

# --- Page Config ---
st.set_page_config(page_title="Tiny Steps", page_icon="🐾", layout="centered")

# --- Custom CSS: Minimal layout adjustments ---
st.markdown("""
    <style>
        /* Tighten action column spacing */
        [data-testid="column"] div.stButton {
            text-align: center;
        }
        
        /* Hover scale effect for the text-only action emojis */
        [data-testid="column"] div.stButton > button:hover {
            transform: scale(1.2);
            transition: transform 0.1s ease-in-out;
            background: transparent !important;
        }
        
        /* Eliminate extra spacing around empty checkboxes */
        [data-testid="stCheckbox"] {
            width: fit-content !important;
            margin-right: 0px !important;
        }
        
        /* Add a bit of padding underneath the tab row for visual breathing room */
        div[data-testid="stTabs"] {
            margin-bottom: 20px;
        }
    </style>
""", unsafe_allow_html=True)

# --- Initialize Session State ---
if "tasks" not in st.session_state:
    st.session_state.tasks = {}

if "completed_archive" not in st.session_state:
    st.session_state.completed_archive = []

if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = True

# --- Helper Functions ---
def add_node(task_tree: dict, parent_id: str, text: str) -> bool:
    """Recursively search for parent_id and add a new subtask."""
    if parent_id is None:
        new_id = str(uuid.uuid4())
        task_tree[new_id] = {"text": text.strip(), "completed": False, "subtasks": {}}
        return True
    
    if parent_id in task_tree:
        new_id = str(uuid.uuid4())
        task_tree[parent_id]["subtasks"][new_id] = {
            "text": text.strip(),
            "completed": False,
            "subtasks": {}
        }
        return True
    
    for node_id, node_data in task_tree.items():
        if add_node(node_data["subtasks"], parent_id, text):
            return True
    return False

def convert_module_output_to_internal_tree(module_breakdown_list: list) -> dict:
    """Recursively maps clean dictionary arrays from the AI helper module into internal UUID nodes."""
    internal_dict = {}
    for item in module_breakdown_list:
        node_id = str(uuid.uuid4())
        internal_dict[node_id] = {
            "text": item["text"].strip(),
            "completed": False,
            "subtasks": convert_module_output_to_internal_tree(item["subtasks"])
        }
    return internal_dict

def update_node_text(task_tree: dict, target_id: str, new_text: str) -> bool:
    """Recursively search for target_id and update its text string."""
    if target_id in task_tree:
        task_tree[target_id]["text"] = new_text.strip()
        return True
    for node_id, node_data in task_tree.items():
        if update_node_text(node_data["subtasks"], target_id, new_text):
            return True
    return False

def toggle_node(task_tree: dict, target_id: str) -> bool:
    """Finds a target task, toggles it, and unchecks parents if the target became unchecked."""
    def process_toggle(tree: dict, target: str) -> tuple[bool, bool]:
        if target in tree:
            tree[target]["completed"] = not tree[target]["completed"]
            return True, (not tree[target]["completed"])
        
        for node_id, node_data in tree.items():
            found, uncheck_parent = process_toggle(node_data["subtasks"], target)
            if found:
                if uncheck_parent:
                    node_data["completed"] = False
                return True, uncheck_parent
        return False, False

    process_toggle(task_tree, target_id)
    return True

def delete_node(task_tree: dict, target_id: str) -> bool:
    """Recursively find and delete a task and its subtasks."""
    if target_id in task_tree:
        del task_tree[target_id]
        return True
    
    for node_id, node_data in task_tree.items():
        if delete_node(node_data["subtasks"], target_id):
            return True
    return False

def archive_completed_main_tasks():
    """Removes only completed MAIN (root) tasks and copies them to the archive."""
    to_archive = []
    for node_id, node_data in list(st.session_state.tasks.items()):
        if node_data["completed"]:
            to_archive.append(node_data["text"])
            del st.session_state.tasks[node_id]
    
    if to_archive:
        st.session_state.completed_archive = to_archive + st.session_state.completed_archive

def count_tasks(task_tree: dict) -> tuple[int, int]:
    """Returns (total_tasks, completed_tasks) across a given tree or branch."""
    total, completed = 0, 0
    for node_id, node_data in task_tree.items():
        total += 1
        if node_data["completed"]:
            completed += 1
        t, c = count_tasks(node_data["subtasks"])
        total += t
        completed += c
    return total, completed

# --- Recursive UI Component ---
def render_task_tree(task_tree: dict, depth=0, parent_id=None):
    """Recursively renders tasks splitting checkboxes from labels cleanly, hiding controls based on edit_mode."""
    for node_id, node_data in list(task_tree.items()):
        current_status = node_data["completed"]
        has_breakdown = len(node_data["subtasks"]) > 0
        
        # --- DYNAMIC COLUMN ALIGNMENT ---
        if st.session_state.edit_mode:
            main_cols_ratio = [0.4, 6.4, 1.2]
            sub_cols_ratio = [depth * 0.4, 0.4, 6.4 - (depth * 0.4), 1.2]
        else:
            main_cols_ratio = [0.4, 7.6]
            sub_cols_ratio = [depth * 0.4, 0.4, 7.6 - (depth * 0.4)]

        if depth == 0:
            cols = st.columns(main_cols_ratio)
            
            with cols[0]:
                checked = st.checkbox(
                    "",
                    value=current_status,
                    key=f"check_{node_id}",
                    label_visibility="collapsed"
                )
                if checked != current_status:
                    toggle_node(st.session_state.tasks, node_id)
                    st.rerun()
                    
            with cols[1]:
                if current_status:
                    st.markdown(f"##### ~~{node_data['text']}~~")
                else:
                    st.markdown(f"##### **{node_data['text']}**")
                    
            if st.session_state.edit_mode:
                action_col = cols[2]
        else:
            cols = st.columns(sub_cols_ratio)
            
            with cols[1]:
                checked = st.checkbox(
                    "",
                    value=current_status,
                    key=f"check_{node_id}",
                    label_visibility="collapsed"
                )
                if checked != current_status:
                    toggle_node(st.session_state.tasks, node_id)
                    st.rerun()
                    
            with cols[2]:
                if current_status:
                    st.markdown(f"└── ~~{node_data['text']}~~")
                else:
                    st.markdown(f"└── {node_data['text']}")
                    
            if st.session_state.edit_mode:
                action_col = cols[3]

        # --- ACTIONS (Rendered in 3 columns only if edit_mode is active) ---
        if st.session_state.edit_mode:
            with action_col:
                sub_col1, sub_col2, sub_col3 = st.columns(3)
                with sub_col1:
                    if not has_breakdown:
                        if st.button("🌿", key=f"break_{node_id}", type="tertiary", help="Break down into a deeper level"):
                            st.session_state[f"show_deep_for_{node_id}"] = True
                            st.session_state[f"show_edit_for_{node_id}"] = False 
                    else:
                        st.write("") 
                with sub_col2:
                    if st.button("✏️", key=f"edit_trigger_{node_id}", type="tertiary", help="Edit step text"):
                        st.session_state[f"show_edit_for_{node_id}"] = True
                        st.session_state[f"show_deep_for_{node_id}"] = False 
                with sub_col3:
                    if st.button("🗑️", key=f"del_{node_id}", type="tertiary", help="Delete Task"):
                        delete_node(st.session_state.tasks, node_id)
                        st.rerun()
                        
            # --- FORM: Edit Text Content ---
            if st.session_state.get(f"show_edit_for_{node_id}", False):
                form_indent = (depth + 1) * 0.4
                form_cols = st.columns([form_indent, 8.0 - form_indent])
                with form_cols[1]:
                    with st.form(key=f"edit_form_{node_id}", clear_on_submit=False):
                        st.write("✏️ *Modify step detail:*")
                        updated_text = st.text_input("Edit text:", value=node_data["text"])
                        f_col1, f_col2 = st.columns([1, 1])
                        with f_col1:
                            if st.form_submit_button("Save Changes", use_container_width=True):
                                if updated_text:
                                    update_node_text(st.session_state.tasks, node_id, updated_text)
                                    st.session_state[f"show_edit_for_{node_id}"] = False
                                    st.rerun()
                                else:
                                    st.error("Task description cannot be left blank!")
                        with f_col2:
                            if st.form_submit_button("Cancel", use_container_width=True):
                                st.session_state[f"show_edit_for_{node_id}"] = False
                                st.rerun()

            # --- FORM: Create Deeper Level ---
            if st.session_state.get(f"show_deep_for_{node_id}", False):
                form_indent = (depth + 1) * 0.4
                form_cols = st.columns([form_indent, 8.0 - form_indent])
                with form_cols[1]:
                    with st.form(key=f"deep_form_{node_id}", clear_on_submit=True):
                        st.write(f"👉 *Creating a new sub-level for: '{node_data['text']}'*")
                        subtext = st.text_input("Enter the first micro-step:", placeholder="e.g., Open the application")
                        f_col1, f_col2 = st.columns([1, 1])
                        with f_col1:
                            if st.form_submit_button("Create Level", use_container_width=True):
                                if subtext:
                                    node_data["completed"] = False 
                                    add_node(st.session_state.tasks, node_id, subtext)
                                    st.session_state[f"show_deep_for_{node_id}"] = False
                                    st.rerun()
                                else:
                                    st.error("A deeper level requires at least one initial task!")
                        with f_col2:
                            if st.form_submit_button("Cancel", use_container_width=True):
                                st.session_state[f"show_deep_for_{node_id}"] = False
                                st.rerun()

        # --- RECURSIVE STEP: Render existing children ---
        if node_data["subtasks"]:
            render_task_tree(node_data["subtasks"], depth = depth + 1, parent_id=node_id)

    # --- INLINE SIBLING BUTTON (Only rendered if edit_mode is active) ---
    if st.session_state.edit_mode and parent_id is not None:
        sibling_indent = depth * 0.4
        remaining_width = 8.0 - sibling_indent
        
        sib_cols = st.columns([sibling_indent, remaining_width - 1.8, 1.8])
        
        with sib_cols[2]:
            if st.button("➕ Add Step", key=f"add_sib_to_{parent_id}", use_container_width=True):
                st.session_state[f"show_sib_for_{parent_id}"] = True
                
        if st.session_state.get(f"show_sib_for_{parent_id}", False):
            form_layout_cols = st.columns([sibling_indent, remaining_width])
            with form_layout_cols[1]:
                with st.form(key=f"sib_form_{parent_id}", clear_on_submit=True):
                    sib_text = st.text_input("New parallel step:", placeholder="What else belongs at this step level?")
                    sf_col1, sf_col2 = st.columns(2)
                    with sf_col1:
                        if st.form_submit_button("Append Step", use_container_width=True):
                            if sib_text:
                                add_node(st.session_state.tasks, parent_id, sib_text)
                                st.session_state[f"show_sib_for_{parent_id}"] = False
                                st.rerun()
                    with sf_col2:
                        if st.form_submit_button("Cancel", use_container_width=True):
                            st.session_state[f"show_sib_for_{parent_id}"] = False
                            st.rerun()

# --- Main App Layout UI ---
st.title("🐾 Tiny Steps")
st.caption("What's the smallest step you could do *and would do*?")
st.divider()

# --- Creation Portals (Manual vs AI Tabs) ---
create_tab1, create_tab2 = st.tabs(["✍️ Manual Entry", "🤖 AI Blueprint Assistant"])

with create_tab1:
    with st.form("add_main_task_form", clear_on_submit=True):
        root_task = st.text_input(
            "Add a top-level goal/task",
            placeholder="e.g., Write essay"
        )
        submitted = st.form_submit_button("Add Main Task", use_container_width=True)
        if submitted:
            if root_task:
                add_node(st.session_state.tasks, None, root_task)
                st.rerun()
            else:
                st.warning("Please enter a task.")

with create_tab2:
    with st.form("ai_task_form", clear_on_submit=False):
        st.write("✨ *Describe a large, vague goal. Gemini will dissolve your initial procrastination blocks by laying out an ultra-incremental, action-ready step layout structure.*")
        ai_prompt = st.text_area(
            "What complex project or goal wants unpacking?",
            placeholder="e.g., Overhaul my backyard garden space, setup a multi-tab web development server environment, compile quarterly tax assets",
            height=85
        )
        ai_submitted = st.form_submit_button("🪄 Generate Micro-Steps", use_container_width=True)
        
        if ai_submitted:
            if not ai_prompt:
                st.warning("Please enter a project description.")
            else:
                with st.spinner("Analyzing complexity and mapping granular starting positions..."):
                    try:
                        # Invoke external helper parsing function
                        blueprint = generate_task_blueprint(ai_prompt)
                        
                        # Generate main framework top-level layer index
                        main_root_id = str(uuid.uuid4())
                        
                        # Build internal task dictionary branch
                        st.session_state.tasks[main_root_id] = {
                            "text": blueprint["main_task_title"],
                            "completed": False,
                            "subtasks": convert_module_output_to_internal_tree(blueprint["breakdown"])
                        }
                        st.toast("Blueprint successfully materialized below! 🎉", icon="🪄")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to generate pipeline structure: {e}")

st.divider()

# --- Display Tree Structure ---
if not st.session_state.tasks:
    st.info("No steps yet. Add your first goal manually or use the AI Assistant above!")
else:
    # Global Overview Progress Calculations
    total, done = count_tasks(st.session_state.tasks)
    st.progress(done / total if total > 0 else 0)
    st.caption(f"**{done}** of **{total}** breakdown steps completed overall across all categories")
    st.divider()
    
    # --- EDIT MODE TOGGLE ROW ---
    edit_col1, edit_col2 = st.columns([6.2, 1.8])
    with edit_col2:
        btn_label = "🔒 Lock View" if st.session_state.edit_mode else "✏️ Edit Steps"
        btn_type = "secondary" if st.session_state.edit_mode else "primary"
        
        if st.button(btn_label, key="toggle_edit_mode", type=btn_type, use_container_width=True):
            st.session_state.edit_mode = not st.session_state.edit_mode
            st.rerun()
            
    # --- ISOLATED TABS IMPLEMENTATION ---
    # Fetch root keys and map titles dynamically 
    main_task_ids = list(st.session_state.tasks.keys())
    tab_titles = [st.session_state.tasks[tid]['text'] for tid in main_task_ids]
    
    # Render Streamlit's native tab bars
    tabs = st.tabs(tab_titles)
    
    # Pinpoint and isolate tree execution contexts to specific tab scopes
    for i, tab in enumerate(tabs):
        with tab:
            tid = main_task_ids[i]
            # Render only the subtree that belongs to this tab's top level root element
            render_task_tree({tid: st.session_state.tasks[tid]})
    
    st.divider()
    
    # Bottom Utility Controls
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🧹 Clear Completed Main Tasks", use_container_width=True):
            archive_completed_main_tasks()
            st.rerun()
    with col2:
        if st.button("🗑️ Clear All", use_container_width=True, type="secondary"):
            st.session_state.tasks = {}
            st.session_state.completed_archive = []
            st.rerun()

# --- Left Sidebar Configurations Using Tabs ---
with st.sidebar:
    st.title("🐾 Control Panel")
    
    side_tab1, side_tab2 = st.tabs(["💡 Strategy", "🏆 Achieved"])
    
    with side_tab1:
        st.header("Structured Flow")
        st.markdown("""
        * Use the **🤖 AI Blueprint Assistant** tab to dynamically construct task architecture via Gemini.
        * Main categories are neatly isolated into **Tabs** to safeguard your cognitive environment.
        * Toggle **✏️ Edit Steps** above the active list to show/hide modification utilities.
        * Use **🌿** to dive a layer deeper (requires you to write out the first micro-step).
        * Use **✏️** next to any item to modify its text value directly inline.
        * Use **➕ Add Step** at the bottom of any block to add more steps to that exact same list level.
        * If you are putting off a task, break it down further. Think, "What is the smallest step I could do that I would do?"
        """)
        st.divider()
        st.caption("Data stays locally in your browser session storage.")
        st.subheader("Completed Main Tasks")

                
    with side_tab2:
        if not st.session_state.completed_archive:
            st.info("No main tasks archived yet. Finish a whole task tree stack and clear it!")
        else:
            for archived_task in st.session_state.completed_archive:
                st.success(f"~~{archived_task}~~")
