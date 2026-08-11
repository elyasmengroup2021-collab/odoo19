/* @odoo-module */

import { FormRenderer } from "@web/views/form/form_renderer";
import { ListController } from "@web/views/list/list_controller";
import { FormController } from "@web/views/form/form_controller";
import { session } from "@web/session";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

patch(FormRenderer.prototype, {
  setup() {
    super.setup();
    this.orm = useService("orm");
    const self = this;

    return Promise.resolve(super.setup()).then(function (ev) {
      var hash = window.location.hash.replace("#", '').split("&");
      let cids;
      let current_company = session.user_companies ? (session.user_companies.current_company || session.company_id) : 1;
      if(hash.findIndex(ele => ele.includes("cid")) == -1)
          cids = current_company;
      else {
          cids = hash.filter(ele => ele.includes("cid"))[0].split("=")[1].split(",");
          cids = cids.length > 0? parseInt(cids[0]): current_company;
      }
      let model = hash.filter(ele=>ele.includes("model"))?.[0];
      model = model? model.split("=")?.[1].split(",")?.[0]: model;
      if (cids && model) {
        self.orm
          .call("access.management", "get_chatter_hide_details", [
            session.uid,
            cids,
            model,
          ])
          .then(function (result) {
            if (!result["hide_send_mail"]) {
              var btn1 = setInterval(function () {
                var el = document.querySelector(".o-mail-Chatter-sendMessage");
                if (el) {
                  el.remove();
                  clearInterval(btn1);
                }
              }, 50);
            }
            if (!result["hide_log_notes"]) {
              var btn2 = setInterval(function () {
                var el = document.querySelector(".o-mail-Chatter-logNote");
                if (el) {
                  el.remove();
                  clearInterval(btn2);
                }
              }, 50);
            }
            if (!result["hide_schedule_activity"]) {
              var btn3 = setInterval(function () {
                var el = document.querySelector(".o-mail-Chatter-activity");
                if (el) {
                  el.remove();
                  clearInterval(btn3);
                }
              }, 50);
            }
          });
      }
    });
  },
});
