package kafka_test

//func manual_test() {
//	ctx := context.Background()
//	store := dto.NewPriceStore()
//	err := godotenv.Load("./.env")
//	if err != nil {
//		log.Fatal("Error loading .env file")
//	}
//	config.LoadConfig()
//	go func() {
//		cfgKafka := server.NewKafkaListenerConfigFromConfig(config.Cfg)
//		err = server.EventKafkaListener(ctx, cfgKafka, server.NewPriceHandler(store))
//	}()
//	if err != nil {
//		log.Fatal(err)
//	}
//	for {
//		time.Sleep(5 * time.Second)
//		for symbol, price := range store.GetAll() {
//			log.Printf("price: %s - %v", symbol, price)
//		}
//		log.Printf("===============")
//	}
//
//}
