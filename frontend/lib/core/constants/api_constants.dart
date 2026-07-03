class ApiConstants {
  ApiConstants._();

  // ============================================================
  // CONFIGURACIÓN DE URL BASE
  // ============================================================
  // Prioridades de configuración:
  // 1. Variable de entorno --dart-define=API_BASE_URL=http://...
  // 2. Valor por defecto según el modo de ejecución
  //
  // Para desarrollo en emulador Android: http://10.0.2.2:8000/
  // Para desarrollo en dispositivo físico: http://TU_IP_LOCAL:8000/
  // Para producción: https://api.tudominio.com/
  // ============================================================

  /// URL base del servidor. Configurable via --dart-define=API_BASE_URL
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    // NOTA: Cambia esta IP a la de tu máquina cuando uses dispositivo físico
    // Para emulador Android usa: http://10.0.2.2:8000/
    // Para iOS Simulator usa: http://localhost:8000/
    defaultValue: 'http://172.20.10.2:8000/',
  );

  /// Modo debug: muestra logs adicionales
  static const bool debugMode = bool.fromEnvironment(
    'DEBUG_MODE',
    defaultValue: true,
  );

  // API Endpoints
  static const String apiPrefix = '/api';

  // Auth
  static const String login = '$apiPrefix/auth/login/';
  static const String refreshToken = '$apiPrefix/auth/refresh/';
  static const String register = '$apiPrefix/auth/register/';
  static const String passwordReset = '$apiPrefix/auth/password-reset/';
  static const String passwordResetConfirm =
      '$apiPrefix/auth/password-reset-confirm/';
  static const String changePassword = '$apiPrefix/auth/change-password/';

  // Users
  static const String users = '$apiPrefix/admin-users/';
  static String userDetail(int id) => '$users$id/';
  static const String galponeros = '${users}galponeros/';

  // Farms
  static const String farms = '$apiPrefix/farms/';
  static String farmDetail(int id) => '$farms$id/';
  static String farmSheds(int farmId) => '$farms$farmId/sheds/';

  // Sheds
  static const String sheds = '$apiPrefix/sheds/';
  static String shedDetail(int id) => '$sheds$id/';

  // Flocks
  static const String flocks = '$apiPrefix/flocks/';
  static String flockDetail(int id) => '$flocks$id/';
  static String flockWeightRecords(int flockId) =>
      '$flocks$flockId/weight-records/';
  static String flockMortalityRecords(int flockId) =>
      '$flocks$flockId/mortality-records/';

  // Inventory
  static const String inventory = '$apiPrefix/inventory/';
  static String inventoryDetail(int id) => '$inventory$id/';
  static String inventoryConsume(int id) => '$inventory$id/consume/';
  static String inventoryAddStock(int id) => '$inventory$id/add-stock/';

  // Alarms
  static const String alarms = '$apiPrefix/alarms/';
  static const String alarmsManage = '$apiPrefix/manage/alarms/';
  static String alarmDetail(int id) => '$alarms$id/';
  static String alarmManageDetail(int id) => '$alarmsManage$id/';
  static String alarmResolve(int id) => '$alarmsManage$id/resolve/';
  static String alarmEscalate(int id) => '$alarmsManage$id/escalate/';
  static const String alarmConfigurations = '$apiPrefix/configs/';

  // Reports
  static const String reports = '$apiPrefix/reports/';
  static String reportDetail(int id) => '$reports$id/';
  static String reportGenerate(int id) => '$reports$id/generate/';
  static String reportDownload(int id) => '$reports$id/download/';
  static const String reportTypes = '${reports}types/';
  static const String quickProductivity = '${reports}quick_productivity/';
  static const String reportTemplates = '$apiPrefix/templates/';

  // Veterinary
  static const String veterinary = '$apiPrefix/veterinary/';
  static const String veterinaryVisits = '${veterinary}visits/';
  static String veterinaryVisitDetail(int id) => '$veterinaryVisits$id/';
  static String veterinaryVisitComplete(int id) =>
      '$veterinaryVisits$id/complete/';
  static const String veterinaryVisitsTodayUpcoming =
      '${veterinaryVisits}today_upcoming/';
  static const String vaccinations = '${veterinary}vaccinations/';
  static String vaccinationDetail(int id) => '$vaccinations$id/';
  static String vaccinationApply(int id) => '$vaccinations$id/apply/';
  static const String vaccinationsUpcoming = '${vaccinations}upcoming/';
  static const String medications = '${veterinary}medications/';
  static String medicationDetail(int id) => '$medications$id/';
  static String medicationRecordApplication(int id) =>
      '$medications$id/record_application/';
  static const String medicationsActive = '${medications}active/';
  static const String medicationsWithdrawal = '${medications}withdrawal/';
  static const String diseases = '${veterinary}diseases/';
  static String diseaseDetail(int id) => '$diseases$id/';
  static const String biosecurityChecklists =
      '${veterinary}biosecurity-checklists/';
  static String biosecurityChecklistDetail(int id) =>
      '$biosecurityChecklists$id/';
  static const String biosecurityComplianceStats =
      '${biosecurityChecklists}compliance_stats/';

  // Alarms - endpoints adicionales
  static const String alarmsDashboard = '${alarmsManage}dashboard/';
  static String alarmAcknowledge(int id) => '$alarmsManage$id/acknowledge/';
  static const String alarmsBulkAcknowledge = '${alarmsManage}bulk-acknowledge/';
  static const String notificationsUnread = '$apiPrefix/notifications/unread/';
  static const String notificationsRecent = '$apiPrefix/notifications/recent/';

  // Flocks - endpoints adicionales
  static const String flocksDashboard = '$apiPrefix/dashboard/';
  static const String flocksImportExcel = '$flocks/import-excel/';
  static const String breedReferences = '$apiPrefix/references/';
  static const String dailyWeights = '$apiPrefix/daily-weights/';
  static const String mortality = '$apiPrefix/mortality/';

  // Inventory - endpoints adicionales
  static const String inventoryStockAlerts = '$inventory/stock-alerts/';
  static const String inventoryBulkUpdateStock =
      '$inventory/bulk-update-stock/';
  static String inventoryConsumeFifo(int id) => '$inventory$id/consume-fifo/';
  static String inventoryFifoBatches(int id) => '$inventory$id/fifo-batches/';

  // ============================================================
  // TIMEOUTS DE RED
  // ============================================================
  // Configurados para manejar conexiones lentas en zonas rurales

  /// Tiempo máximo para establecer conexión
  static const Duration connectionTimeout = Duration(seconds: 30);

  /// Tiempo máximo para recibir respuesta del servidor
  static const Duration receiveTimeout = Duration(seconds: 30);

  /// Tiempo máximo para enviar datos al servidor
  static const Duration sendTimeout = Duration(seconds: 30);

  /// Timeout corto para operaciones rápidas (health check, etc.)
  static const Duration shortTimeout = Duration(seconds: 10);

  // Headers
  static Map<String, String> get defaultHeaders => {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  };

  static Map<String, String> authHeaders(String token) => {
    ...defaultHeaders,
    'Authorization': 'Bearer $token',
  };
}
