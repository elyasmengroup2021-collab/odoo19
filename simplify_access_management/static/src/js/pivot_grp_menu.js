/** @odoo-module **/
import { PivotRenderer } from "@web/views/pivot/pivot_renderer";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { onWillStart } from "@odoo/owl";

patch(PivotRenderer.prototype, {
  setup() {
    super.setup(...arguments);
    this.orm = useService("orm");
    this.hiddenGroupByFields = [];
    onWillStart(async () => {
      const res = await this.orm.call("access.management", "get_hidden_field", [
        "",
        this?.env?.searchModel?.resModel,
      ]);
      this.hiddenGroupByFields = res || [];
    });
  },
  get groupByItems() {
    const items = super.groupByItems;
    if (this.hiddenGroupByFields && this.hiddenGroupByFields.length) {
      return items.filter(
        (ele) => !this.hiddenGroupByFields.includes(ele.fieldName ?? ele.name)
      );
    }
    return items;
  },
});
