class Accounts {

    newAccountType() {
        let form = ``;
        form += fom.text('name','',true)
        form += fom.textarea('description',2,true)
        form += fom.selectv2('normal_balance',[{val:'DR',desc:"Debit"},{val:"CR",desc:"Credit"}],'',true)

        amodal.setBodyHtml(form)
        amodal.setTitleText("Create New Account Type")
        amodal.setFooterHtml(`<button class="btn btn-sm btn-success save_new_account_type">SAVE</button>`)
        amodal.show()

        $('.save_new_account_type').click(async function () {
            let ids = ['mypk','name','description','normal_balance'];
            if(anton.validateInputs(ids)){
                let payload = {
                    module:'account_type',
                    data:anton.Inputs(ids)
                }

                await api.v2('PUT',payload,'/accounts/api/').then(response => {
                    kasa.confirm(response.message,1,'here')
                }).catch(error => {kasa.error(error)})

            } else {
                kasa.error("invalid Form")
            }
        })

    }

    async loadAccountType() {
        await this.getAccountType('*').then(response => {
            if(anton.IsRequest(response)){
                let message = response['message'];
                let tr = "";
                message.map(at => {
                    console.table(at)
                    tr += `
                        
                        <tr>
                            <td class="px-4 py-3">
                                <div class="fw-bold text-dark">${at.name} (${at.normal_balance})</div>
                            </td>
                            <td class="px-4 py-3 text-muted small">${at.description}</td>
                            <td class="px-4 py-3 text-end fw-bold text-success">${at.balance}</td>
                            <td class="px-4 py-3 text-center">
                                <button data-code="${at.code}" class="btn btn-light btn-sm text-primary edit_account_type"><i class="fas fa-edit"></i></button>
                            </td>
                        </tr>
                        
                    `
                })

                $('tbody').html(tr)

                $('.edit_account_type').click(function (){
                    let code = $(this).data('code');
                    kasa.info(`Editing account type ${code}`)
                })
            } else {
                kasa.response(response)
            }
        }).catch(error => {kasa.error(error)})
    }

    async getAccountType(code='*') {
        return api.call('VIEW',{
            module:"account_type",
            data:{
                code:code
            }
        },'/accounts/api/')
    }

    async getLedger(code='*'){
        return api.call("VIEW",{
            module:'ledger',
            data:{
                code:code
            }
        },'/accounts/api/')
    }

    async loadLedger(){
        await this.getLedger().then(response => {
            if(anton.IsRequest(response)){
                 let data = response.message;
                 let tr = "";
                 data.map(led => {
                     console.table(led)
                     tr += `
                        <tr>
                            <td class="px-4 py-3">
                                <div class="fw-bold text-dark">${led.name}</div>
                            </td>
                            <td class="px-4 py-3 text-muted small">${led.description}</td>
                            <td class="px-4 py-3 text-end fw-bold text-success">${led.balance}</td>
                            <td class="px-4 py-3 text-center">
                                <button title="Sub Ledger" class="btn btn-light btn-sm text-primary"><i class="fas fa-tree"></i></button>
                            </td>
                        </tr>
                     `
                 })

                $('tbody').html(tr)
            } else {
                kasa.response(response)
            }
        }).catch(error => {kasa.error(error)})
    }

    async newLedger() {
        let form = ``;
        let op = []
        await this.getAccountType('*').then(response => {
            if(anton.IsRequest(response)){
                response.message.map(lt => {
                    op.push({
                        val:lt.code,desc:`${lt.normal_balance} - ${lt.name}`
                    })
                })
            } else {
                kasa.error(response.message);
                return
            }
        })
        form += fom.selectv2('account_type',op,'',true)
        form += fom.text('name','',true)
        form += fom.textarea('description',2,true)
        form += fom.text('sledge','',true)


        amodal.setBodyHtml(form)
        amodal.setTitleText("Create New Ledger")
        amodal.setFooterHtml(`<button class="btn btn-sm btn-success save_new_ledger">SAVE</button>`)
        amodal.show()

        $('.save_new_ledger').click(async function () {
            let ids = ['mypk','name','description','account_type','sledge'];
            if(anton.validateInputs(ids)){
                let payload = {
                    module:'ledger',
                    data:anton.Inputs(ids)
                }

                await api.v2('PUT',payload,'/accounts/api/').then(response => {
                    kasa.confirm(response.message,1,'here')
                }).catch(error => {kasa.error(error)})

            } else {
                kasa.error("invalid Form")
            }
        })
    }
}

const accountant = new Accounts()