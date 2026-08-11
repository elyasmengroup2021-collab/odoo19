/* @odoo-module */
import { ActionMenus } from "@web/search/action_menus/action_menus";
import { patch } from "@web/core/utils/patch";


patch(ActionMenus.prototype, {
  async getActionItems(props) {
    let res = await super.getActionItems(props);
    const RestActions = await this.orm.call("access.management","get_remove_options",[1, props.resModel]);
    return res.filter((ele) => !RestActions.includes(ele.key));
  },
});
