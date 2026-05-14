import geopandas as gpd
import pandas as pd
import osmnx as ox
import networkx as nx
import numpy as np
import json
import folium
import random
import streamlit as st
from streamlit_folium import st_folium
import os
DATA_DIR = os.path.dirname(os.path.abspath(__file__))

# Data Loading Functions

@st.cache_resource
def load_graph():
    G = ox.load_graphml(os.path.join(DATA_DIR, 'iceland_drive_accessible.graphml'))
    return G, ox.convert.to_undirected(G)

@st.cache_data
def load_attractions():
    df = gpd.read_file(os.path.join(DATA_DIR, 'alternative_attractions_processed.geojson'))
    df['category'] = df['category'].str.split('•').apply(lambda x: [i.strip() for i in x] if isinstance(x, list) else x)
    df['group'] = df['group'].str.split('•').apply(lambda x: [i.strip() for i in x] if isinstance(x, list) else x)
    return df

@st.cache_data
def load_distance_matrix():
    dist_df = pd.read_csv(os.path.join(DATA_DIR, 'distance_matrix.csv'), index_col=0)
    dist_df.index = dist_df.index.map(lambda x: int(float(x)))
    dist_df.columns = dist_df.columns.map(lambda x: int(float(x)))
    dist_df = dist_df[~dist_df.index.duplicated(keep='first')]
    dist_df = dist_df.loc[:, ~dist_df.columns.duplicated(keep='first')]
    return dist_df

@st.cache_data
def load_config():
    with open(os.path.join(DATA_DIR, 'config.json'), 'r') as f:
        config = json.load(f)
    return config['keflavik_node']

#  Step 1: Load everything once
G, G_undirected = load_graph()
alternative_attractions_df = load_attractions()
dist_df = load_distance_matrix()
keflavik_node = load_config()

# Sidebar Input (User)

st.title("Iceland Alternative Route Planner")

with st.sidebar:
    st.header("Plan your trip")
    N_DAYS = st.slider("How many days is your trip?", min_value=3, max_value=10, value=5)
    SELECTED_GROUPS = st.multiselect(
        "What kind of experiences are you interested in?",
        options=['Nature/Adventure', 'Sightseeing', 'Culture', 'Services', 'Leisure'],
        default=['Nature/Adventure', 'Sightseeing']
    )
    if len(SELECTED_GROUPS) == 0:
        st.warning("Please select at least one category of interest.")
        st.stop()
    generate = st.button("Generate Route")

    st.info("Warning: Each click generates a new unique route.")

    st.info("Note: The Average off the beaten path information is calculated by taking the average of the hiddem gem scores of each attraction"
    " and presenting them as a percentage.")

# Routing and Output

if generate:
    with st.spinner("Generating your route..."):
        RANDOM_SEED = random.randint(0, 1000)

        # Step 2: Define constant parameters (no user input)
        DAILY_BUDGET_KM = 300
        MAX_STOPS_PER_DAY = 5
        TOP_N_ANCHORS = 10
        SECONDARY_RADIUS_KM = 50
        SECONDARY_RADIUS_EXPANDED_KM = 80
        MIN_SECONDARIES = 2

        # Step 3: Filter by user's category selection

        df_filtered = alternative_attractions_df[
            alternative_attractions_df['group'].apply(
                lambda x: any(g in SELECTED_GROUPS for g in x) if isinstance(x, list) else x in SELECTED_GROUPS
            )
        ].copy()

        if len(df_filtered) < N_DAYS * 3:
            st.warning(f"Only {len(df_filtered)} attractions found for your selected categories. Consider adding more interests.")
            st.stop()
        
        # Step 4: Filter by reachability

        total_budget_m = N_DAYS * DAILY_BUDGET_KM * 1000
        max_reach_m = total_budget_m / 2
        kef_row = dist_df.loc[keflavik_node]
        kef_row = kef_row[~kef_row.index.duplicated(keep='first')]
        kef_dist_dict = {int(float(k)): v for k, v in kef_row.to_dict().items()}
        df_filtered['dist_to_kef'] = df_filtered['node_id'].map(kef_dist_dict)
        df_filtered = df_filtered[df_filtered['dist_to_kef'] <= max_reach_m].copy()

        # Step 5: Initialize routing variables

        current_node = keflavik_node
        visited_ids = set()
        itinerary = []
        remaining_days = N_DAYS
        anchor_nodes_visited = [keflavik_node]

        # Step 6: Routing Loop

        for day in range(N_DAYS):

            # STEP 1 - eligibility check
            if remaining_days == 1:
                max_dist_from_kef = DAILY_BUDGET_KM * 1000
            else:
                max_dist_from_kef = (remaining_days - 1) * DAILY_BUDGET_KM * 1000

            eligible = df_filtered[
                (~df_filtered.index.isin(visited_ids)) &
                (df_filtered['dist_to_kef'] <= max_dist_from_kef) &
                (df_filtered['node_id'].map(lambda n: dist_df.at[current_node, n]) <= DAILY_BUDGET_KM * 1000)
            ].copy()

            # STEP 2 - ensure onward options exist
            if day < N_DAYS - 1:
                def has_onward_options(node):
                    reachable_from_node = df_filtered[
                        (~df_filtered.index.isin(visited_ids)) &
                        (df_filtered['node_id'].map(lambda n: dist_df.at[node, n]) <= DAILY_BUDGET_KM * 1000)
                    ]
                    return len(reachable_from_node) > 0
                eligible = eligible[eligible['node_id'].map(has_onward_options)].copy()

            # STEP 3 - anchor selection
            distance_from_current = eligible['node_id'].map(lambda n: dist_df.at[current_node, n])

            if 1 <= day <= N_DAYS - 2:
                eligible_band = eligible[
                    (distance_from_current >= 100 * 1000) &
                    (distance_from_current <= DAILY_BUDGET_KM * 1000)
                ].copy()
            elif day == N_DAYS - 1:
                eligible_band = eligible[
                    (distance_from_current >= 50 * 1000) &
                    (distance_from_current <= DAILY_BUDGET_KM * 1000)
                ].copy()
            else:
                eligible_band = eligible

            def too_close_to_previous_anchors(node):
                return any(
                    dist_df.at[node, prev_anchor] < 50 * 1000
                    for prev_anchor in anchor_nodes_visited
                )

            eligible_band = eligible_band[
                ~eligible_band['node_id'].map(too_close_to_previous_anchors)
            ].copy()

            if len(eligible_band) < TOP_N_ANCHORS:
                eligible_band = eligible

            top_candidates = eligible_band.nlargest(TOP_N_ANCHORS, 'hiddengem_score')

            if len(top_candidates) == 0:
                st.warning(f"Day {day+1}: no eligible attractions found, route ended early.")
                break

            weights = top_candidates['hiddengem_score'].tolist()
            if sum(weights) == 0:
                weights = None

            anchor = top_candidates.sample(n=1, weights=weights, random_state=RANDOM_SEED + day).iloc[0]
            anchor_node = anchor['node_id']

            # STEP 4 - secondary attractions
            dist_from_anchor = eligible['node_id'].map(lambda n: dist_df.at[anchor_node, n])

            secondaries = eligible[
                (eligible.index != anchor.name) &
                (dist_from_anchor <= SECONDARY_RADIUS_KM * 1000)
            ].copy()

            if len(secondaries) < MIN_SECONDARIES:
                secondaries = eligible[
                    (eligible.index != anchor.name) &
                    (dist_from_anchor <= SECONDARY_RADIUS_EXPANDED_KM * 1000)
                ].copy()

            top_secondary_candidates = secondaries.nlargest(TOP_N_ANCHORS, 'hiddengem_score')
            
            if len(top_secondary_candidates) > 0:
                weights = top_secondary_candidates['hiddengem_score'].tolist()
                n_to_sample = min(MAX_STOPS_PER_DAY - 1, len(top_secondary_candidates))
                if sum(weights) <= 0 or any(w < 0 for w in weights):
                    weights = None
                secondaries = top_secondary_candidates.sample(
                    n=n_to_sample,
                    weights=weights,
                    random_state=RANDOM_SEED + day + 100,
                    replace=False)

            # STEP 5 - update itinerary
            dist_to_anchor = distance_from_current[anchor.name]
            estimated_daily_dist = dist_to_anchor + (SECONDARY_RADIUS_KM * 1000)

            day_route = [anchor] + secondaries.to_dict('records')

            visited_ids.add(anchor.name)
            for _, sec in secondaries.iterrows():
                visited_ids.add(sec.name)

            current_node = anchor['node_id']
            anchor_nodes_visited.append(anchor_node)
            remaining_days -= 1

            itinerary.append({
                'day': day + 1,
                'anchor': anchor['name'],
                'stops': [anchor['name']] + secondaries['name'].tolist(),
                'municipality': anchor['municipality'],
                'driving_km': distance_from_current[anchor.name] / 1000
            })

            itinerary[-1]['anchor_dist_from_kef'] = dist_df.at[keflavik_node, anchor_node]

        # Step 7: Reordering the Route

        sorted_by_dist = sorted(itinerary, key=lambda d: d['anchor_dist_from_kef'], reverse=True)
        midpoint = len(sorted_by_dist) // 2
        outward = sorted_by_dist[:midpoint + 1]
        returning = sorted_by_dist[midpoint + 1:]
        reordered = outward + returning
        for i, day_data in enumerate(reordered):
            day_data['day'] = i + 1
        reordered_itinerary = reordered

        # Step 8: Retrieve Road Geometries for Route

        all_day_coords = []
        markers = []

        for day_data in reordered_itinerary:
            day_idx = day_data['day'] - 1
            day_segments = []

            if day_data['day'] == 1:
                start_node = keflavik_node
            else:
                prev_anchor = reordered_itinerary[day_idx - 1]['anchor']
                start_node = df_filtered[df_filtered['name'] == prev_anchor].iloc[0]['node_id']

            day_nodes = [start_node]
            for stop in day_data['stops']:
                stop_rows = df_filtered[df_filtered['name'] == stop]
                if len(stop_rows) > 0:
                    day_nodes.append(stop_rows.iloc[0]['node_id'])

            for i in range(len(day_nodes) - 1):
                origin = day_nodes[i]
                destination = day_nodes[i + 1]
                try:
                    route = nx.shortest_path(G_undirected, origin, destination, weight='length')
                    coords = [[G_undirected.nodes[n]['y'], G_undirected.nodes[n]['x']] for n in route]
                    day_segments.extend(coords)
                except nx.NetworkXNoPath:
                    st.warning(f"No path found between nodes {origin} and {destination}, skipping segment.")

            all_day_coords.append(day_segments)

            for stop in day_data['stops']:
                stop_rows = df_filtered[df_filtered['name'] == stop]
                if len(stop_rows) == 0:
                    continue
                stop_row = stop_rows.iloc[0]
                is_anchor = stop == day_data['anchor']
                markers.append({
                    'lat': stop_row.geometry.y,
                    'lon': stop_row.geometry.x,
                    'name': stop,
                    'day': day_idx,
                    'is_anchor': is_anchor
                })

        markers.append({'lat': 63.9850, 'lon': -22.6056, 'name': 'Keflavik Airport', 'day': -1, 'is_anchor': True})

        # Step 9: Folium Map to Visualize the Route

        m = folium.Map(location=[64.9631, -19.0208], zoom_start=6)

        day_colors = ['blue', 'red', 'green', 'purple', 'orange',
                    'darkblue', 'darkred', 'darkgreen', 'cadetblue', 'black']

        for day_idx, day_coords in enumerate(all_day_coords):
            color = day_colors[day_idx % len(day_colors)]
            folium.PolyLine(
                locations=day_coords,
                color=color,
                weight=3,
                opacity=0.8,
                tooltip=f"Day {day_idx + 1}"
            ).add_to(m)

        for marker in markers:
            if marker['day'] == -1:
                folium.Marker(
                    location=[marker['lat'], marker['lon']],
                    popup="Keflavik Airport",
                    icon=folium.Icon(color='black', icon='plane', prefix='fa')
                ).add_to(m)
            else:
                color = day_colors[marker['day'] % len(day_colors)]
                if marker['is_anchor']:
                    folium.Marker(
                        location=[marker['lat'], marker['lon']],
                        popup=f"Day {marker['day']+1} anchor: {marker['name']}",
                        icon=folium.Icon(color=color, icon='star', prefix='fa')
                    ).add_to(m)
                else:
                    folium.CircleMarker(
                        location=[marker['lat'], marker['lon']],
                        radius=7,
                        color='white',
                        weight=2,
                        fill_color=color,
                        fill_opacity=0.8,
                        popup=f"Day {marker['day']+1}: {marker['name']}"
                    ).add_to(m)

        folium.LayerControl().add_to(m)
        st_folium(m, width=900)

        # Step 10: Add Itinerary Information

        summary_lines = ["## Your Iceland Alternative Route\n"]

        total_driving = 0
        total_stops = 0

        for day_data in reordered_itinerary:
            summary_lines.append(f"**Day {day_data['day']} — {day_data['municipality']}**")
            summary_lines.append(f"Main destination: {day_data['anchor']}")
            summary_lines.append(f"Also visiting:")
            for stop in day_data['stops'][1:]:
                summary_lines.append(f"- {stop}")

            day_scores = []
            for stop in day_data['stops']:
                stop_rows = df_filtered[df_filtered['name'] == stop]
                if len(stop_rows) > 0:
                    day_scores.append(stop_rows.iloc[0]['hiddengem_score'])
            if day_scores:
                summary_lines.append(f"Average off the beaten path: {sum(day_scores)/len(day_scores) * 100:.0f}%")

            summary_lines.append("")
            total_driving += day_data['driving_km']
            total_stops += len(day_data['stops'])

        all_scores = []
        for day_data in reordered_itinerary:
            for stop in day_data['stops']:
                stop_rows = df_filtered[df_filtered['name'] == stop]
                if len(stop_rows) > 0:
                    all_scores.append(stop_rows.iloc[0]['hiddengem_score'])

        summary_lines.append(f"**Total attractions visited: {total_stops}**")
        summary_lines.append(f"**Overall off the beaten path: {sum(all_scores)/len(all_scores) * 100:.0f}%**")

        st.markdown("\n\n".join(summary_lines))
        st.session_state['map'] = m._repr_html_()
        st.session_state['summary'] = "\n\n".join(summary_lines)


# Display stored outputs if they exist - OUTSIDE if generate block
if 'map' in st.session_state:
    tab1, tab2 = st.tabs(["Map", "Itinerary"])
    with tab1:
        st.components.v1.html(st.session_state['map'], width=900, height=600)
    with tab2:
        st.markdown(st.session_state['summary'])
    st.download_button(
        label="Download Itinerary",
        data=st.session_state['summary'],
        file_name="iceland_itinerary.txt",
        mime="text/plain"
    )



