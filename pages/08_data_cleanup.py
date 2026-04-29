import json

import streamlit as st

from data_cleanup import find_similar_names, load_mappings, save_mappings
from sidebar import render_filters

st.set_page_config(page_title="Data Cleanup", page_icon="🧹", layout="wide")
st.title("🧹 Data Cleanup")
st.caption(
    "Detect and fix misspelled or inconsistent names that are being split across "
    "separate rows in your charts. Mappings are saved to name_mappings.json and "
    "applied automatically to every page."
)

_, df_all, trip_clients = render_filters()

if "cleanup_mappings" not in st.session_state:
    st.session_state.cleanup_mappings = load_mappings()

mappings = st.session_state.cleanup_mappings

entity_config = [
    {
        "key": "clients",
        "label": "👤 Clients",
        "names": (
            trip_clients["Client_Name"].dropna().tolist()
            if not trip_clients.empty and "Client_Name" in trip_clients.columns
            else []
        ),
    },
    {
        "key": "suppliers",
        "label": "🏨 Suppliers",
        "names": (
            df_all["Supplier_Name"].dropna().tolist()
            if not df_all.empty and "Supplier_Name" in df_all.columns
            else []
        ),
    },
    {
        "key": "destinations",
        "label": "🌍 Destinations",
        "names": (
            df_all["Destination"].dropna().tolist()
            if not df_all.empty and "Destination" in df_all.columns
            else []
        ),
    },
]

tabs = st.tabs([cfg["label"] for cfg in entity_config])

for tab, cfg in zip(tabs, entity_config):
    key = cfg["key"]
    names = cfg["names"]
    current_map: dict = mappings.setdefault(key, {})

    with tab:
        col_left, col_right = st.columns([3, 2], gap="large")

        # ── Left: duplicate detection ──────────────────────────────────────────
        with col_left:
            st.subheader("Potential Duplicates")
            threshold = st.slider(
                "Similarity threshold",
                70, 100, 85, 5,
                key=f"thresh_{key}",
                help="Raise to see fewer but more confident matches. Lower reveals more candidates.",
            )

            similar = find_similar_names(names, threshold)
            # Only show pairs where neither name has already been mapped away
            similar = [
                p for p in similar
                if p["name_a"] not in current_map and p["name_b"] not in current_map
            ]

            if not similar:
                st.success("No potential duplicates found at this threshold.")
            else:
                st.caption(f"{len(similar)} potential duplicate pair(s) — adjust threshold to tune results.")
                for i, pair in enumerate(similar[:30]):
                    with st.container(border=True):
                        top_cols = st.columns([5, 5, 2])
                        top_cols[0].markdown(f"**{pair['name_a']}**")
                        top_cols[1].markdown(f"**{pair['name_b']}**")
                        top_cols[2].markdown(f"`{pair['score']}%`")

                        bot_cols = st.columns([5, 5, 2])
                        canonical = bot_cols[0].selectbox(
                            "Keep as canonical",
                            [pair["name_a"], pair["name_b"]],
                            key=f"can_{key}_{i}",
                            label_visibility="collapsed",
                        )
                        variant = (
                            pair["name_b"] if canonical == pair["name_a"] else pair["name_a"]
                        )
                        bot_cols[1].caption(f"Will map: ~~{variant}~~ → **{canonical}**")
                        if bot_cols[2].button("Merge", key=f"merge_{key}_{i}", type="primary"):
                            current_map[variant] = canonical
                            save_mappings(mappings)
                            st.session_state.cleanup_mappings = mappings
                            st.cache_data.clear()
                            st.rerun()

        # ── Right: manual mapping + active mappings ────────────────────────────
        with col_right:
            st.subheader("Add Manual Mapping")
            st.caption("Use when a pair isn't detected automatically.")
            with st.form(key=f"manual_{key}"):
                variant_in = st.text_input("Variant (wrong / alternate spelling)")
                canonical_in = st.text_input("Canonical (the correct name to keep)")
                if st.form_submit_button("Add mapping"):
                    v, c = variant_in.strip(), canonical_in.strip()
                    if v and c and v != c:
                        current_map[v] = c
                        save_mappings(mappings)
                        st.session_state.cleanup_mappings = mappings
                        st.cache_data.clear()
                        st.rerun()
                    elif v == c:
                        st.warning("Variant and canonical must differ.")

            st.markdown("---")
            st.subheader("Active Mappings")
            if current_map:
                st.caption(f"{len(current_map)} mapping(s) active — applied to all charts automatically.")
                for variant, canonical in list(current_map.items()):
                    row = st.columns([4, 4, 1])
                    row[0].markdown(f"~~{variant}~~")
                    row[1].markdown(f"→ **{canonical}**")
                    if row[2].button("✕", key=f"del_{key}_{variant}", help="Remove this mapping"):
                        del current_map[variant]
                        save_mappings(mappings)
                        st.session_state.cleanup_mappings = mappings
                        st.cache_data.clear()
                        st.rerun()
            else:
                st.info("No mappings defined yet for this entity type.")

        st.markdown("---")
        st.download_button(
            "⬇ Download name_mappings.json",
            data=json.dumps(mappings, indent=2, sort_keys=True),
            file_name="name_mappings.json",
            mime="application/json",
            key=f"download_{key}",
            help=(
                "On Streamlit Cloud, mappings reset when the app restarts. "
                "Download this file and commit it to your repo to make them permanent."
            ),
        )
