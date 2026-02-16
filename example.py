import time

from sound_player import AudioLayer, Sound, SoundPlayer


def test_sound():
    print("Test sound:")
    sound = Sound("data/music.ogg")

    sound.play()
    time.sleep(3)

    sound.pause()
    time.sleep(2)

    sound.play()
    time.sleep(3)

    sound.stop()
    time.sleep(2)


def test_playlist():
    print("Test audio layer")
    pl = AudioLayer(concurrency=2)
    pl.enqueue(Sound("data/coin.wav"))
    pl.enqueue(Sound("data/music.ogg"))
    pl.enqueue(Sound("data/coin.wav"))
    pl.enqueue(Sound("data/coin.wav"))

    pl.play()
    time.sleep(10)
    pl.stop()
    time.sleep(2)


def test_sound_player():
    print("Test player")
    player = SoundPlayer()
    player.create_audio_layer(1)

    # first player
    player.enqueue(Sound("data/coin.wav"), 1)
    player.enqueue(Sound("data/music.ogg"), 1)
    player.enqueue(Sound("data/coin.wav"), 1)

    player.play()
    time.sleep(5)

    # second player
    player.create_audio_layer(2)
    player.enqueue(Sound("data/coin.wav"), 2)
    player.enqueue(Sound("data/coin.wav"), 2)
    time.sleep(10)
    player.stop()
    time.sleep(1)


def test_sound_audio_layer_loop():
    print("Test audio layer loop")
    pl = AudioLayer(concurrency=2)
    pl.set_loop(-1)

    sound = Sound("data/coin.wav")
    sound.set_loop(5)
    pl.enqueue(sound)

    pl.play()
    time.sleep(5)
    pl.stop()
    time.sleep(2)


if __name__ == "__main__":
    test_sound()
    test_playlist()
    test_sound_player()
    test_sound_audio_layer_loop()
