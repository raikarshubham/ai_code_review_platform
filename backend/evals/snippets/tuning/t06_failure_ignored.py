import logging

log = logging.getLogger(__name__)


def checkout(payment_api, order):
    try:
        payment_api.charge(order.customer_id, order.total)
    except ConnectionError:
        log.warning("payment service unreachable")
    # expect: bug
    order.status = "paid"
    return order
