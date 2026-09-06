from pathlib import Path
from threading import Thread

from app.services.save_dialog import SaveDialogBroker


def test_save_dialog_broker_returns_main_thread_choice_to_worker():
    broker = SaveDialogBroker()
    result = {}

    def request_destination():
        result['value'] = broker.choose('客户 A_效果图.png')

    worker = Thread(target=request_destination)
    worker.start()

    request = broker.next_request(timeout=0.5)
    assert request.initial_name == '客户 A_效果图.png'
    broker.resolve(request, Path('C:/exports/客户 A_效果图.png'))

    worker.join(timeout=0.5)
    assert not worker.is_alive()
    assert result['value'] == Path('C:/exports/客户 A_效果图.png')
