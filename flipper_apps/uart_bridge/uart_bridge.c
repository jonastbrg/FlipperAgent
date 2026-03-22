/**
 * UART Bridge — USB CDC Channel 1 ↔ GPIO UART @ 115200.
 *
 * Switches Flipper to dual-CDC USB mode. A second serial port appears on
 * the computer. Anything sent to that port goes to the ESP32 Marauder via
 * GPIO UART, and responses come back the same way.
 *
 * Channel 0 = Flipper CLI (unchanged)
 * Channel 1 = ESP32 Marauder bridge (new port)
 *
 * Press BACK to exit (restores single-CDC mode).
 */

#include <furi.h>
#include <furi_hal.h>
#include <furi_hal_usb.h>
#include <furi_hal_usb_cdc.h>
#include <gui/gui.h>
#include <gui/view_port.h>

#define UART_CH FuriHalSerialIdUsart
#define BAUDRATE 115200
#define BRIDGE_CDC_CH 1
#define BUF_SIZE 512

typedef struct {
    FuriStreamBuffer* uart_rx_stream;
    FuriHalSerialHandle* serial_handle;
    FuriThread* rx_thread;
    FuriThread* tx_thread;
    volatile bool running;
    uint32_t bytes_rx;
    uint32_t bytes_tx;
} UartBridge;

// IRQ: byte from GPIO UART (ESP32) → stream buffer
static void uart_irq_cb(FuriHalSerialHandle* handle, FuriHalSerialRxEvent event, void* ctx) {
    UartBridge* b = ctx;
    if(event == FuriHalSerialRxEventData) {
        uint8_t byte = furi_hal_serial_async_rx(handle);
        furi_stream_buffer_send(b->uart_rx_stream, &byte, 1, 0);
    }
}

// Thread: GPIO UART → USB CDC ch1 (ESP32 responses to computer)
static int32_t rx_worker(void* ctx) {
    UartBridge* b = ctx;
    uint8_t buf[BUF_SIZE];
    while(b->running) {
        size_t len = furi_stream_buffer_receive(b->uart_rx_stream, buf, BUF_SIZE, 50);
        if(len > 0) {
            furi_hal_cdc_send(BRIDGE_CDC_CH, buf, (uint16_t)len);
            b->bytes_rx += len;
        }
    }
    return 0;
}

// Thread: USB CDC ch1 → GPIO UART (computer commands to ESP32)
static int32_t tx_worker(void* ctx) {
    UartBridge* b = ctx;
    uint8_t buf[BUF_SIZE];
    while(b->running) {
        int32_t len = furi_hal_cdc_receive(BRIDGE_CDC_CH, buf, BUF_SIZE);
        if(len > 0) {
            furi_hal_serial_tx(b->serial_handle, buf, (size_t)len);
            furi_hal_serial_tx_wait_complete(b->serial_handle);
            b->bytes_tx += len;
        } else {
            furi_delay_ms(10);
        }
    }
    return 0;
}

static void draw_cb(Canvas* canvas, void* ctx) {
    UartBridge* b = ctx;
    canvas_clear(canvas);
    canvas_set_font(canvas, FontPrimary);
    canvas_draw_str(canvas, 2, 12, "UART Bridge");
    canvas_set_font(canvas, FontSecondary);
    canvas_draw_str(canvas, 2, 26, "2nd USB port <-> ESP32");
    canvas_draw_str(canvas, 2, 38, "Marauder @ 115200 baud");
    char s[48];
    snprintf(s, sizeof(s), "To ESP: %lu  From ESP: %lu",
        (unsigned long)b->bytes_tx, (unsigned long)b->bytes_rx);
    canvas_draw_str(canvas, 2, 52, s);
    canvas_draw_str(canvas, 2, 64, "[BACK] to exit");
}

static void input_cb(InputEvent* event, void* ctx) {
    FuriMessageQueue* q = ctx;
    furi_message_queue_put(q, event, FuriWaitForever);
}

int32_t uart_bridge_app(void* p) {
    UNUSED(p);

    // Save current USB mode and switch to dual CDC
    FuriHalUsbInterface* prev_usb = furi_hal_usb_get_config();
    furi_hal_usb_unlock();
    furi_hal_usb_set_config(&usb_cdc_dual, NULL);
    furi_delay_ms(500); // Let USB re-enumerate

    UartBridge b = {
        .uart_rx_stream = furi_stream_buffer_alloc(BUF_SIZE * 4, 1),
        .running = true,
        .bytes_rx = 0,
        .bytes_tx = 0,
    };

    // Open GPIO UART to ESP32
    b.serial_handle = furi_hal_serial_control_acquire(UART_CH);
    furi_check(b.serial_handle);
    furi_hal_serial_init(b.serial_handle, BAUDRATE);
    furi_hal_serial_async_rx_start(b.serial_handle, uart_irq_cb, &b, false);

    // Start bridge threads
    b.rx_thread = furi_thread_alloc_ex("UartBrRx", 1024, rx_worker, &b);
    furi_thread_start(b.rx_thread);
    b.tx_thread = furi_thread_alloc_ex("UartBrTx", 1024, tx_worker, &b);
    furi_thread_start(b.tx_thread);

    // GUI
    FuriMessageQueue* eq = furi_message_queue_alloc(8, sizeof(InputEvent));
    ViewPort* vp = view_port_alloc();
    view_port_draw_callback_set(vp, draw_cb, &b);
    view_port_input_callback_set(vp, input_cb, eq);
    Gui* gui = furi_record_open(RECORD_GUI);
    gui_add_view_port(gui, vp, GuiLayerFullscreen);

    InputEvent event;
    while(b.running) {
        if(furi_message_queue_get(eq, &event, 200) == FuriStatusOk) {
            if(event.type == InputTypePress && event.key == InputKeyBack) {
                b.running = false;
            }
        }
        view_port_update(vp);
    }

    // Cleanup
    gui_remove_view_port(gui, vp);
    furi_record_close(RECORD_GUI);
    view_port_free(vp);
    furi_message_queue_free(eq);

    furi_thread_join(b.rx_thread);
    furi_thread_join(b.tx_thread);
    furi_thread_free(b.rx_thread);
    furi_thread_free(b.tx_thread);

    furi_hal_serial_async_rx_stop(b.serial_handle);
    furi_hal_serial_deinit(b.serial_handle);
    furi_hal_serial_control_release(b.serial_handle);
    furi_stream_buffer_free(b.uart_rx_stream);

    // Restore USB mode
    furi_hal_usb_set_config(prev_usb, NULL);

    return 0;
}
