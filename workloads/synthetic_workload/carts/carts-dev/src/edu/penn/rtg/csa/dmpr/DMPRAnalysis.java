package edu.penn.rtg.csa.dmpr;

import edu.penn.rtg.common.*;


/**
 * Class CacheAwareMPRAnalysis
 * It's the start point of the cache aware MPR analysis
 * It parse the input xml file, call the Component.java to analysis the system recursively and 
 * output the result to output xml file.
 * 
 * JDK version used: <JDK1.7>
 * @author Meng Xu
 * Create Date: 4/6/2013 
 *
 */
public class DMPRAnalysis {
	public static void process(String[] args){
		if(args.length < 3){
			error();
		}
		
		try{
			if(args.length == 3){
				//DEFAULT SCHED TEST!
				int whichSchedTest = GlobalVariable.ARVIND_SCHEDTEST; //ARVIND_SCHEDTEST;//BERTOGNA_SCHEDTEST
				System.out.println("Command is:" + args[0] + " " + args[1] + " " + args[2] + " whichSchedTest="+ whichSchedTest);
				run(args[0],args[1],args[2],whichSchedTest);
			}else if(args.length >= 4){ // >= to make it easier in eclipse to debug.
				int whichSchedTest = parseWhichSchedTest(args[3]);
				run(args[0],args[1],args[2],whichSchedTest);
			}
		}catch(Exception e){
			e.printStackTrace();
			System.err.println("Exception trown out in the analysis");
		}
	}
	
	public static void run(String inputFilename, String resourceModel, String outputFilename, int whichSchedTest){

		XMLInterpreter4DMPR xmlInterpreter = new XMLInterpreter4DMPR(inputFilename); //4 is short for "for"
		
		xmlInterpreter.parseFile();
		Component rootComponent = xmlInterpreter.getRootComponent();
		
		doCSAhEDF(rootComponent,whichSchedTest);
		
		XMLWriter4DMPR xmlWriter = new XMLWriter4DMPR(outputFilename, rootComponent);
		xmlWriter.writeComponentInterfaceTree();
		
	}
	
	public static int parseWhichSchedTest(String str){
		if(str.equalsIgnoreCase("ARVIND_SCHEDTEST")) return GlobalVariable.ARVIND_SCHEDTEST;
		if(str.equalsIgnoreCase("BERTOGNA_SCHEDTEST")) return GlobalVariable.BERTOGNA_SCHEDTEST;
		if(str.equalsIgnoreCase("ARVIND_SCHEDTEST_FAST")) return GlobalVariable.ARVIND_SCHEDTEST_FAST;
		if(str.equalsIgnoreCase("MENG_SCHEDTEST")) return GlobalVariable.MENG_SCHEDTEST;
		
		System.err.println("In parseWhichSchedTest() No such sched test! System exit.");
		System.exit(1);
		return 0;
	}
	
	private static void error() {
		System.err.println("Invalid arguments");
		System.err
				.println("Carts <input_XML_file> <scheduling_algo> <output_XML_file>");
		System.err
		.println("<scheduling_algo> can be : PRM / EDP / EQV / MPR / DMPR / CADMPR_TASKCENTRIC / CADMPR_MODELCENTRIC / CADMPR_HYBRID");
		System.exit(1);
		
	}
	
	public static String doCSAhEDF(Component rootComponent, int whichSchedTest){
		String result = checkSchedulingAlgorithm(rootComponent);
		rootComponent.doCSA(whichSchedTest);
		return result;
	}
	

	public static String checkSchedulingAlgorithm(Component rootComponent){
		String result = "";
		if (!(rootComponent.getSchedulingPolicy().equalsIgnoreCase("hEDF")
				|| rootComponent.getSchedulingPolicy().equalsIgnoreCase("EDF") || rootComponent
				.getSchedulingPolicy().equalsIgnoreCase("gEDF"))) {
			return "ERROR: only support hEDF scheduling policy in each component with DMPR model";
		}
		for (Component component : rootComponent.getChildComponents()) {
			// EDF is considered as gEDF by default
			String child_result = checkSchedulingAlgorithm(component);
			if(!child_result.contains("SUCCESS")){
				return child_result;
			}
			
		}

		return "SUCCESS!";
	}
}
