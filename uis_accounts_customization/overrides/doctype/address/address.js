frappe.ui.form.on('Address', {
    setup(frm) {
        frm.set_df_property("city", "reqd", 0);
        frm.set_df_property("city", "hidden", 1);
        frm.trigger("country");
        frm.trigger("custom_state_province");
    },

    country(frm) {
        const state_filters = {
            country: ['in', frm.doc.country || null]
        };
        if (frm.is_dirty()) {
            frm.set_value("custom_state_province", "");
        }
        uis_accounts_customization.utils.create_state_city_filter(frm, "custom_state_province", state_filters);
    },

    custom_state_province(frm) {
        const city_filters = {
            state_province: ['in', frm.doc.custom_state_province || null]
        };
        if (frm.is_dirty()) {
            frm.set_value("custom_custom_city", "");
        }
        uis_accounts_customization.utils.create_state_city_filter(frm, "custom_custom_city", city_filters);
    },

    custom_custom_city(frm) {
        if (frm.is_dirty()) {
            frm.set_value("city", frm.doc.custom_custom_city);
        }
    }
});

frappe.ui.form.on("Address", {
    custom_google_map_link: function (frm) {
        const url = frm.doc.custom_google_map_link;
        if (!url) { return; }

        frappe.call({
            method: "uis_accounts_customization.overrides.doctype.address.address.extract_lat_lng_from_maps_url",
            args: { url: url },
            callback: function (r) {
                if (!r || !r.message) { frappe.msgprint("No response from coordinate extractor."); return; }

                let data = r.message;
                if (typeof data === "string") {
                    try { data = JSON.parse(data); } catch (e) { frappe.msgprint("Unexpected response format."); return; }
                }
                if (!data.ok) { frappe.msgprint(data.message || "Could not extract coordinates."); return; }

                const lat = data.lat;
                const lng = data.lng;

                frm.set_value("custom_latitude", String(lat));
                frm.set_value("custom_longitude", String(lng));

                const feature = {
                    type: "Feature",
                    geometry: { type: "Point", coordinates: [Number(lng), Number(lat)] },
                    properties: {}
                };
                frm.set_value("custom_map_view", JSON.stringify(feature));
                setTimeout(function () { tune_geolocation_ui(frm); }, 300);
            }
        });
    },

    custom_map_view: function (frm) {
        const raw = frm.doc.custom_map_view;
        if (!raw) { return; }

        let v = raw;
        if (typeof raw === "string") {
            try { v = JSON.parse(raw); } catch (e) { return; }
        }

        if (v && typeof v === "object") {
            if (v.lat && v.lng) {
                frm.set_value("custom_latitude", String(v.lat));
                frm.set_value("custom_longitude", String(v.lng));
            } else if (
                v.type === "Feature" &&
                v.geometry &&
                v.geometry.type === "Point" &&
                Array.isArray(v.geometry.coordinates) &&
                v.geometry.coordinates.length >= 2
            ) {
                const lng = v.geometry.coordinates[0];
                const lat = v.geometry.coordinates[1];
                frm.set_value("custom_latitude", String(lat));
                frm.set_value("custom_longitude", String(lng));
            }
        }

        setTimeout(function () { tune_geolocation_ui(frm); }, 300);
    },

    refresh: function (frm) {
        // Add "View in Google Maps" button
        frm.add_custom_button("View in Google Maps", function () {
            const link = frm.doc.custom_google_map_link;
            const has_link = !!link && link.trim() !== "";
            if (has_link) {
                window.open(link, "_blank", "noopener");
                return;
            }

            const has_lat = !!frm.doc.custom_latitude && frm.doc.custom_latitude !== "";
            const has_lng = !!frm.doc.custom_longitude && frm.doc.custom_longitude !== "";
            if (has_lat && has_lng) {
                const lat = String(frm.doc.custom_latitude).trim();
                const lng = String(frm.doc.custom_longitude).trim();
                const url = "https://www.google.com/maps?q=" + encodeURIComponent(lat + "," + lng);
                window.open(url, "_blank", "noopener");
                return;
            }

            frappe.msgprint("Provide either Google Map Link or Latitude/Longitude to open in Google Maps.");
        });

        // Ensure map has a pin if lat/lng exist
        const hasLat = frm.doc.custom_latitude && frm.doc.custom_latitude !== "";
        const hasLng = frm.doc.custom_longitude && frm.doc.custom_longitude !== "";
        const hasMap = !!frm.doc.custom_map_view;

        if (!hasMap && hasLat && hasLng) {
            const lat = parseFloat(frm.doc.custom_latitude);
            const lng = parseFloat(frm.doc.custom_longitude);
            if (!isNaN(lat) && !isNaN(lng)) {
                const feature = {
                    type: "Feature",
                    geometry: { type: "Point", coordinates: [Number(lng), Number(lat)] },
                    properties: {}
                };
                frm.set_value("custom_map_view", JSON.stringify(feature));
            }
        }

        setTimeout(function () { tune_geolocation_ui(frm); }, 300);
    }
});

/* ------------------------------- Helpers ------------------------------- */

function tune_geolocation_ui(frm) {
    const fieldname = "custom_map_view";
    const fld = frm.fields_dict[fieldname];
    if (!fld) { return; }

    const map = fld.map;
    if (!map || typeof L === "undefined") { return; }

    // Replace any existing basemap tile with Carto Voyager (English)
    map.eachLayer(function (layer) {
        if (layer instanceof L.TileLayer) {
            map.removeLayer(layer);
        }
    });

    const cartoTiles = L.tileLayer(
        "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
        {
            maxZoom: 19,
            attribution:
                '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> ' +
                '&copy; <a href="https://carto.com/attributions">CARTO</a>'
        }
    );
    cartoTiles.addTo(map);

    // Remove/disable all plugin toolbars (e.g., Geoman)
    if (map.pm && typeof map.pm.removeControls === "function") {
        map.pm.removeControls();
    }
    if (map.pm && typeof map.pm.addControls === "function") {
        map.pm.addControls({
            position: "topleft",
            drawMarker: false,
            drawPolyline: false,
            drawRectangle: false,
            drawPolygon: false,
            drawCircle: false,
            editMode: false,
            dragMode: false,
            cutPolygon: false,
            removalMode: false
        });
    }

    // Keep only the zoom control visible
    const style_id = "only-zoom-controls-style";
    if (!document.getElementById(style_id)) {
        const style = document.createElement("style");
        style.id = style_id;
        style.textContent =
            ".leaflet-control-container .leaflet-top.leaflet-left > *:not(.leaflet-control-zoom){display:none !important;}" +
            ".leaflet-control-container .leaflet-top.leaflet-right > *{display:none !important;}" +
            ".leaflet-control-container .leaflet-bottom.leaflet-left > *{display:none !important;}" +
            ".leaflet-control-container .leaflet-bottom.leaflet-right > *{display:none !important;}";
        document.head.appendChild(style);
    }

    if (map.zoomControl && typeof map.zoomControl.addTo === "function") {
        map.zoomControl.addTo(map);
    }

    // Recenter on the current point if present (use GeoJSON in field)
    const raw = frm.doc[fieldname];
    if (!raw) { return; }

    try {
        const val = typeof raw === "string" ? JSON.parse(raw) : raw;
        const is_point =
            val &&
            val.type === "Feature" &&
            val.geometry &&
            val.geometry.type === "Point" &&
            Array.isArray(val.geometry.coordinates) &&
            val.geometry.coordinates.length >= 2;

        if (is_point) {
            const lng = Number(val.geometry.coordinates[0]);
            const lat = Number(val.geometry.coordinates[1]);
            if (!Number.isNaN(lat) && !Number.isNaN(lng)) {
                map.setView([lat, lng], 14);
            }
        }
    } catch (e) {
        // ignore parse errors
    }
}