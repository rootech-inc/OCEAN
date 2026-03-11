class Logistics {
    interface = '/logistic/api/';

    async LoadDeliveries(status = 'pending') {
        await this.getDeliveries(status).then(response => {
            if (anton.IsRequest(response)) {
                let message = response.message;
                let data = [];
                console.log(message);
                message.forEach(delivery => {
                    data.push([
                        delivery.requested_by ? delivery.requested_by.name : '',
                        delivery.destination ?? '',
                        delivery.request_date ?? '',
                        delivery.status ?? '',
                        `<button data-enc="${delivery.enc}" class="btn view_delivery btn-sm btn-primary">View</button>` // Action column (HTML)
                    ]);
                });



                if ($.fn.DataTable.isDataTable('#del')) {

                    var table = $('#del').DataTable();
                    table.clear();
                    table.rows.add(data);
                    table.draw();
                } else {
                    $('#del').DataTable({
                        data: data,
                        responsive: true,
                        columnDefs: [
                            { targets: 0, createdCell: (td) => $(td).attr('data-label', 'Requested By') },
                            { targets: 1, createdCell: (td) => $(td).attr('data-label', 'Destination') },
                            { targets: 2, createdCell: (td) => $(td).attr('data-label', 'Request Date') },
                            {
                                targets: 3,
                                createdCell: (td, cellData) => {
                                    $(td).attr('data-label', 'Status');
                                    const statusClass = `status-${cellData.toLowerCase().replace(' ', '_')}`;
                                    $(td).html(`<span class="badge ${statusClass}">${cellData}</span>`);
                                }
                            },
                            { targets: 4, createdCell: (td) => $(td).attr('data-label', 'Action').addClass('text-end') }
                        ],
                        dom: 'rtip', // Hide default search/length as we have custom ones
                        language: {
                            paginate: {
                                previous: '<i class="bi bi-chevron-left"></i>',
                                next: '<i class="bi bi-chevron-right"></i>'
                            }
                        }
                    });
                }

                $('.view_delivery').click(function () {
                    location.href = `/logistic/delivery/view/${$(this).data('enc')}/`
                    // windowPopUp(`/logistic/delivery/view/${$(this).data('enc')}/`,"Delivery Information",600,800)
                })

                console.table(data)
            } else {
                kasa.response(response)
            }
        }).catch(err => { kasa.error(err) });
    }

    async getDeliveries(status = 'pending', against = 'in', enc = '*') {
        return api.call('VIEW', {
            module: 'delivery_request',
            data: {
                'pk': enc,
                status: status,
                against: against,
            }
        }, this.interface)
    }

    async LoadDeliveryDetails(enc) {
        await this.getDeliveries('*', '*', enc).then(response => {
            if (anton.IsRequest(response)) {
                let message = response.message[0];
                console.table(message)
                $('.source').text(message.source)
                $('.destination').text(message.destination)
                $('.description').text(message.description)
                $('.requested_by').text(message.requested_by.name)
                $('.request_date').text(message.request_date)
                let bu_ht = ""
                let status = message.status;
                let btn_color, btn_text, btn_status;
                switch (status) {
                    case 'pending':
                        btn_color = 'info'
                        btn_text = 'Schedule'
                        btn_status = 'schedule'
                        break;
                    case 'schedule':
                        btn_color = 'warning'
                        btn_text = 'Deliver'
                        btn_status = 'in_transit'
                        break;
                    case 'in_transit':
                        btn_color = 'success'
                        btn_text = 'END'
                        btn_status = 'delivered'
                        bu_ht += `<button  class="btn btn-sm btn-info update_trip ms-2"><i class="fa fa-upload"></i></button>`;
                        break;
                    default:
                        btn_text = ''
                        btn_color = 'text-light'
                }


                if (status !== 'delivered') {
                    bu_ht += `<button data-changeto="${btn_status}" class="btn xgh_del btn-sm btn-${btn_color} ms-2">${btn_text}</button>`;
                }

                let logs_ht = ""
                message.logs.map(log => {
                    logs_ht += `
                         <div class="mb-4 position-relative">
                          <div class="rounded-circle bg-success position-absolute" style="left: -32px; top: 0; width: 20px; height: 20px; ${log === message.logs.length - 1 ? 'border-bottom: none;' : ''}"></div>
                          <div class="font-weight-bold">${log.title}</div>
                          <div class="text-muted small">${log.details}</div>
                          <div class="text-muted small">${log.time}</div>
                        </div>
                    `
                })

                $('.bt').html(bu_ht)

                $('.logs').html(logs_ht)

                $('.xgh_del').click(async function () {
                    if (confirm('Are you sure you want to change the status of this delivery?')) {
                        let changeto = $(this).data('changeto');
                        let enc = message.enc;
                        let payload = {
                            module: 'delivery_request',
                            data: {
                                enc: enc,
                                status: changeto,
                                user: $('#mypk').val()
                            }
                        }

                        console.table(payload)
                        // select car and driver
                        let loader_html = `
                                <div class="shc_screen">
                                    
                                    <div class="spinner-border text-primary x_spin mb-3" role="status">
                                        <span class="visually-hidden">Loading...</span>
                                    </div>
                                   
                                </div>
                            `



                        amodal.setBodyHtml(loader_html)
                        amodal.setTitleHtml(`${changeto} Delivery`)
                        amodal.setFooterHtml(`<button disabled class="btn btn-success" id="make_schedule_button">COMPLETE</button>`)
                        amodal.show()
                        $('.shc_screen').prepend(fom.textarea('remarks', 5, true))



                        if (changeto === "schedule") {

                            $('.shc_screen').prepend(fom.date_local('schedule_time', '', true))

                            // load driver
                            await api.v2('VIEW', { module: 'driver', data: { pk: '*' } }, logistics.interface).then(response => {
                                if (anton.IsRequest(response)) {
                                    let drivers = []
                                    response.message.map(driver => {
                                        drivers.push({ val: driver.pk, desc: driver.name })
                                    })

                                    let driver_form = fom.selectv2('driver', drivers, '', true)
                                    $('.shc_screen').prepend(driver_form)
                                    $('.x_spin').remove()
                                    $('#make_schedule_button').attr('disabled', false)


                                } else {
                                    kasa.response(response)
                                }
                            }).catch(err => { kasa.error(err) });

                        }

                        if (changeto === "in_transit") {
                            $('.shc_screen').prepend(fom.date_local('departure_time', '', true))
                            // load cars
                            let cars = api.call('VIEW', { module: 'vehicle', data: { pk: '*' } }, logistics.interface);
                            if (anton.IsRequest(cars)) {
                                let carss = []
                                cars.message.map(car => {
                                    carss.push({
                                        val: car.pk, desc: `${car.plate_number} - ${car.description}`
                                    })
                                })
                                let cars_form = fom.selectv2('vehicle', carss, '', true)
                                $('.shc_screen').prepend(cars_form)
                                $('.x_spin').remove()
                                $('#make_schedule_button').attr('disabled', false)
                            } else {
                                $('.shc_screen').prepend(cars.message)
                            }
                        }

                        if (changeto === "delivered") {
                            $('.x_spin').remove()
                            $('.shc_screen').prepend(fom.date_local('end_time', '', true))
                            $('#make_schedule_button').attr('disabled', false)
                        }

                        $('#make_schedule_button').click(async function () {
                            let ids = ['remarks']
                            if (changeto === "schedule") {

                                ids.push('schedule_time')
                                ids.push('driver')

                                payload['data']['driver'] = $('#driver').val()
                                payload['data']['schedule_time'] = $('#schedule_time').val()
                            }

                            if (changeto === "in_transit") {
                                ids.push('departure_time')
                                ids.push('vehicle')
                                payload['data']['vehicle'] = $('#vehicle').val()
                                payload['data']['departure_time'] = $('#departure_time').val()
                            }

                            if (changeto === "delivered") {
                                ids.push('end_time')
                                payload['data']['end_time'] = $('#end_time').val()
                            }

                            if (anton.validateInputs(ids)) {
                                payload['data']['remarks'] = $('#remarks').val()
                                console.table(payload)
                                await api.v2('PATCH', payload, logistics.interface).then(response => {
                                    if (anton.IsRequest(response)) {
                                        logistics.LoadDeliveries(enc);
                                        kasa.success('Operation Successful')
                                        amodal.hide()
                                    } else {
                                        kasa.response(response)
                                    }
                                }).catch(err => { kasa.error(err) });

                            }
                        })
                    } else {
                        kasa.info('Process Cancelled')
                    }


                })

                $('.update_trip').click(function () {
                    let form = "";
                    form += fom.text('title')
                    form += fom.textarea('details')

                    amodal.setBodyHtml(form)
                    amodal.setTitleHtml("Update Trip")
                    amodal.setFooterHtml(`<button class="btn btn-success" id="uptrp">Save</button>`)
                    amodal.show()

                    $('#uptrp').click(async function () {
                        let ids = ['title', 'details']
                        if (anton.validateInputs(ids)) {
                            let payload = {
                                module: 'trip_log',
                                data: {
                                    enc: enc,
                                    title: $('#title').val(),
                                    details: $('#details').val(),
                                    user: $('#mypk').val()
                                }
                            }

                            await api.v2('PUT', payload, logistics.interface).then(response => {
                                if (anton.IsRequest(response)) {
                                    kasa.confirm(response.message, 1, 'here')
                                } else {
                                    kasa.response(response)
                                }
                            }).catch(err => { kasa.error(err) });
                        }
                    })

                })

            } else {
                kasa.response(response)
            }
        }).catch(err => { kasa.error(err) });
    }

    async loadDrivers() {
        await this.getDrivers().then(response => {
            let ht = ""
            if (anton.IsRequest(response)) {
                response.message.map(driver => {
                    console.table(driver)
                    let st = ""
                    if (driver.is_engaged) {
                        st = "alert-danger"
                    }
                    ht += `
                        <div class="col-12 col-sm-6 col-lg-4 mb-4">
                            <div class="card h-100 border-0 shadow-sm hover-shadow transition-all ${st}" style="border-radius: 16px; overflow: hidden;">
                                <div class="card-body p-0">
                                    <div class="d-flex align-items-center p-4">
                                        <div class="flex-shrink-0">
                                            <div class="rounded-circle overflow-hidden shadow-sm" style="width: 70px; height: 70px; border: 3px solid #fff;">
                                                <img src="${driver.db}" class="img-fluid h-100 w-100" style="object-fit: cover;" alt="${driver.name}">
                                            </div>
                                        </div>
                                        <div class="ms-3 flex-grow-1">
                                            <h5 class="mb-1 font-weight-bold text-dark">${driver.name}</h5>
                                            <div class="d-flex align-items-center">
                                                <span class="badge ${driver.is_engaged ? 'bg-danger' : 'bg-success'} rounded-pill me-2" style="font-size: 0.7rem;">
                                                    ${driver.is_engaged ? 'Busy' : 'Available'}
                                                </span>
                                                <small class="text-muted"><i class="bi bi-person-badge me-1"></i> Driver</small>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="px-4 pb-4">
                                        <div class="bg-light rounded-lg p-3 d-flex justify-content-between align-items-center">
                                            <div>
                                                <small class="text-uppercase text-muted font-weight-bold px-0" style="font-size: 0.65rem; letter-spacing: 0.05em;">Total Deliveries</small>
                                                <div class="h5 mb-0 font-weight-bold text-primary">${driver.deliveries}</div>
                                            </div>
                                            <button class="btn btn-sm btn-outline-primary rounded-pill px-3">Details</button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    `
                })
            } else {
                ht = response.message
            }

            $('#drivers').html(ht)
        }).catch(err => { kasa.error(err) });
    }

    getDrivers() {
        return api.v2("ViEW", { module: 'driver', data: { pk: '*' } }, logistics.interface)
    }

    newDriver() {
        let form = "";
        // get all users
        let all_users = user.allUsers()
        let opts = []
        if (anton.IsRequest(all_users)) {

            all_users.message.map(user => {
                console.log(user)
                opts.push({ val: user.pk, desc: user.fullname })
            })
        } else {
            kasa.response(all_users)
            return false
        }
        console.table(all_users)
        form += fom.selectv2('user', opts, '', true)
        form += fom.text('license_number', "", true)
        form += `
            <form action="/logistic/upload-diver-image/" id="update_image" method="POST" enctype="multipart/form-data">
                <div class="form-group">
                    <label for="image">SELFIE</label>
                    <input type="file" accept="image/*" name="image" id="image">
                </div>
                <div class="form-group">
                    <label for="license">LICENSE</label>
                    <input type="file" accept="image/*" name="image" id="image">
                </div>
                <input type="hidden" name="license" id="license">
            </form>
        `



        amodal.setBodyHtml(form)
        amodal.setTitleHtml("Add Driver")
        amodal.show()
        amodal.setFooterHtml(`<button class="btn btn-success" id="save_new_driver">Save Drivers</button>`)


        $('#save_new_driver').on('click', async function () {
            let ids = ['user', 'mypk', 'image', 'license_number']
            if (anton.validateInputs(ids)) {
                let payload = {
                    module: 'driver',
                    data: anton.Inputs(ids)
                }
                // payload['data']['user'] = $('#mypk').val()

                await api.v2('PUT', payload, logistics.interface).then(response => {
                    if (anton.IsRequest(response)) {
                        $('#driver').val(response.message)
                        $('#update_image').submit()
                    } else {
                        kasa.response(response)
                    }
                }).catch(err => { kasa.error(err) });
            }
        })
    }

    async loadFleets() {
        await this.getFleet().then(response => {
            let ht = ""
            if (anton.IsRequest(response)) {


                response.message.map(fleet => {
                    console.table(fleet)
                    ht += `
                        <div class="col-md-3 mb-4">
                          <div class="card shadow-sm border-0">
                              <img src="${fleet.img}" class="card-img-top" alt="Car Image">
                              <div class="card-body text-center">
                              <h5 class="card-title mb-1">${fleet.plate_number}</h5>
                              <p class="card-text text-muted ellipsis" title="${fleet.description}">${fleet.description}</p>
                            </div>
                          </div>
                        </div>
                    `
                })

                $('#fleets').html(ht)
            } else {
                $('#fleets').html(response.message)
            }
        }).catch(err => { kasa.error(err) });
    }

    async getFleet(pk = '*') {
        return api.call("ViEW", { module: 'vehicle', data: { pk: pk } }, logistics.interface)
    }

    async loadFleet(pk) {
        console.log(pk)
        await this.getFleet(pk).then(response => {

            if (anton.IsRequest(response)) {
                let fleet = response.message[0];
                console.table(fleet)
                anton.setValues(fleet)

                $('#img').attr('src', fleet.img)

                if (fleet.next > 0) {
                    $('#next').attr('disabled', false)
                    $('#next').attr('data-pk', fleet.next)
                } else {
                    $('#next').attr('disabled', true)
                }

                if (fleet.previous > 0) {
                    $('#previous').attr('disabled', false)
                    $('#previous').attr('data-pk', fleet.prev)
                } else {
                    $('#previous').attr('disabled', true)
                }

            } else {
                console.log(response)
            }
        }).catch(err => { kasa.error(err) });
    }

    async weeklyReport() {
        let payload = {
            module: 'weekly_report',
            data: {}
        }

        await api.v2('VIEW', payload, logistics.interface).then(response => {
            if (anton.IsRequest(response)) {
                let file = response.message;
                anton.viewFile(`/${file}`)
            } else {
                kasa.response(response)
            }
        }).catch(err => {
            kasa.error(err)
        })
    }
}

const logistics = new Logistics();