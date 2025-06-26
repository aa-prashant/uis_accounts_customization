(() => {
  // ../uis_accounts_customization/uis_accounts_customization/public/js/utils.js
  frappe.provide("uis_accounts_customization.utils");
  $.extend(uis_accounts_customization.utils, {
    create_state_city_filter(frm, fieldName, filter_obj) {
      frm.set_query(fieldName, () => {
        return {
          filters: filter_obj
        };
      });
    }
  });
})();
//# sourceMappingURL=uis_accounts_customization.bundle.R4TQKPY5.js.map
